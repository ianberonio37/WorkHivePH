# Skill writeback proposal — P-program deepwalk, 2026-09-05

_One-pass approval table (CLAUDE.md "Skill Self-Improvement Loop"). Each row is a lesson verified today in the
UFAI trajectory program's round 1–4 pain registers (UFAI_TRAJECTORY_ROADMAP.md, "P-program · 2026-09-05" sections).
X = the skill gets a rule written from its own angle. Nothing is written to any SKILL.md until Ian approves._

| # | Lesson (verified today) | QA | Frontend | Perf | Mobile | Security | Multitenant | Data Eng | DevOps | Designer | Analytics |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | The sweep signed in by membership ROW ORDER (`limit(1).maybeSingle()`) and graded the worker hive as the supervisor page — resolve identity role-first, then hive; a harness that picks "any membership" grades a different page | X | | | | | X | | | | |
| 2 | Ten root pages had never been on the family board (Poppins never loaded ×4; a 1,519 px page); a page outside the board is invisible — `board-covers-roster` gate now binds the board to the roster | X | | | | | | | X | | |
| 3 | Six transform-closed `role=dialog` sheets on marketplace read as six OPEN modals to every a11y lens — a closed sheet must also be `visibility:hidden` (transition-delayed) | X | X | | X | | | | | X | |
| 4 | A guest masthead painted `display:flex` then hidden on `DOMContentLoaded` = CLS 0.16; decide identity-dependent chrome SYNCHRONOUSLY from stored identity right after it parses | X | X | X | X | | | | | | |
| 5 | An empty provenance-chip slot filled 46 px after paint; a JS "paint-first" is moot when every render awaits a registry fetch — reserve heights in CSS at PARSE time (`#ds-axes` 335/579, chip 30/46) | | X | X | X | | | | | | |
| 6 | The rubric's one named CLS "culprit" is a VICTIM (trust-bar, `div.main`); fixes built from it moved 0.197 by nothing. The instrument must explain its own number: every shift, every source, prev→current rect, the viewport — `WH_SWEEP_CLS_DEBUG=1`, I1 graded from a settled pre-survey snapshot | X | X | X | | | | | | | |
| 7 | founder-console's first screen at 1280×720: grid panels paint ~100 px and settle at 2,065/440 px, pushing row two out of view (CLS 0.48) — every 390 px probe had them below the fold; match the gate's viewport before re-measuring; reserve settled heights | X | X | X | X | | | | | | |
| 8 | Four founder tiles were COUNTED client-side from capped reads (`.limit(10000/50000/20000)` vs 155k rows): active hives 4 vs 5, index views 5,555 vs 12,466, "MAU" keyed anon rows on `Math.random()`. A cap that feeds a DISTINCT/COUNT/SUM is a wrong number — roll up in the DB (SECURITY INVOKER fns, RLS still applies) and define the metric (identified viewers ≠ anonymous sessions) | X | X | X | | X | X | X | | | X |
| 9 | Chromium restores form values on a same-URL navigation: a harness that searched a page then re-opened it inherited a stale query and read an empty list (INV4 red in-phase only). `autocomplete="off"` on list-driving inputs; harness clears on reach; enrich the journey's OWN evidence before theorising | X | X | | X | | | | | | |
| 10 | Two K-phase journeys (LA4, PMK5) read red only under six-chrome contention and passed alone in 0.8 s / 8.1 s — a red under load is re-run serially before it is a finding; the K phases run one at a time on this 8 GB host | X | | X | | | | | X | | |
| 11 | T4 "1/1 scroll container chains to the page" on every calculator/learn page named none of their CSS — the container was the shared feedback panel (`div.wh-fb-body`): contain overscroll where the scroll container IS, not on `html` | | X | | X | | | | | | |
| 12 | "Home 22 px" and a 36 px brand link were the shared header partial (`build_pillar_pages.SITE_HEADER`), not the pages; `.5rem` padding then overflowed 390 by 13 px — targets grow in min-width/min-height, not padding, and the generator owns the fix | | X | | X | | | | X | X | |
| 13 | `← Back to WorkHive` (my own W1 fix) shipped at 114×17 on every internal page; two pages don't load utils.js so the shared rule can't reach them — a shared CSS fix must check who loads the sheet | X | X | | X | | | | | | |
| 14 | A reference catalog's table cells are DATA, not copy: B1/B2/B3/B5/G2/H4/L1 graded 2,424 validator labels as marketese — on `wh-page-kind=reference` the copy lenses skip `table, pre, code` (documented contract, the ruler not the page) | X | | | | | | | | | |
| 15 | `advance_trajectory` refused `fixing → fixed` as a regress: its ORDER listed the finished state before the in-flight one — a regress guard encodes the workflow's order, never the alphabet's | X | | | | | | | X | | |
| 16 | A reference page's "cap is not a total" had NO scanning gate (the DB-grants gate `no-client-truncate` is not a page scanner; `at-cap-fits`/`printed-truncation` are fixed lists) — new `reference-pages-uncapped`: every `.limit(N)`/`.slice(0,N)` list read is disclosed or annotated `cap-ok` (date slices 10/16/19 excluded) | X | X | | | | | X | X | | |
| 17 | A platform gate "covers everything" only over its ROSTER: `displayed-values` scanned 29 DB pages, `control-within-viewport` 23, `prove_safe_area` 22, `one-clock-per-string` / `clickable-keyboard-a11y` root pages only (no `learn/`) — every one missed the reference pages. A row locks on a gate only after the gate demonstrably scans the page, and growing the roster is part of landing the row (roster +7, glob + `learn/*.html`, +platform-actions, +learn/index) | X | | | X | | | X | X | | |
| 18 | Semantic red/green (`#f87171`/`#4ade80`) read Lc 45–47/60 on 21–23 px KPI numerals — text needs the lighter tints (`#fca5a5`/`#86efac`), declared AFTER the semantic rules so the cascade wins | | X | | | | | | | X | |
| 19 | The memory index reached 20.7 KB of doctrine the compactor may not retire — a family collapse (one line per class, members on disk and Memento-retrievable) is the honest reduction (46 lines → 7 family lines, 17.8 KB) | | | | | | | | X | | |
| 20 | Staged calculators verified at 95 with target dims clear while their registry rows point at the LIVE `tools/<slug>` pages — a staged verify advances a row to `fixing`, never `fixed`; promotion is Ian's gate | X | | | | | | | X | | |
| 21 | "Cross-hive read refusal" and "write-authz depth" are provable as DATA per page: `SET LOCAL ROLE authenticated` + jwt claims for a single-hive member, count rows (a USING clause filters → 0 rows; a WITH CHECK raises → 42501), and always prove the control (own hive > 0 / own insert allowed) inside a rolled-back transaction — four recipes today (llm-observability, founder-console ×2, project-manager) | X | | | | X | X | X | | | |
| 23 | `rtConn()` paints connection state only: rows inserted while a realtime channel is down never arrive, and nothing re-fetched on re-subscribe or `online` — a page that listens must backfill on the first SUBSCRIBED after a drop and refresh on `online` (founder-console feedback inbox; proved live by cutting the network mid-subscription) | X | X | | | | | | | | |
| 24 | Sticky table headers pinned at `top: 0` and full-screen overlays with `inset: 0` sit under the notch — `top: env(safe-area-inset-top, 0px)` / notch padding; the safe-area prover flagged both only once its roster included the reference pages | | X | | X | | | | | X | |
| 25 | The reference surfaces had four un-instrumented lens families (the fourth state, a claim a query enforces, the log is greppable, systemic ripple) — each became a live prover in a day (`reference-fourth-state`, `reference-claims` + EXPLAIN, `page-log-tags`, `reference-shared-ripple`, `sw-navigation-fallback`, `reference-repaint-focus`): when a cell "cannot be live", the move is to build the instrument, not to call it covered-by-nature | X | | | | | | | X | | |
| 26 | A page-scanning gate over a grown roster names every capped read, but a `.limit(N)` is only a defect when something PAINTED derives from it — classify each site by what the next 30 lines do with the rows (a list → `cap-ok` with the reason; a count/sum → exact server count or a `+`/"latest N" disclosure), and teach the gate that `.slice(0, N)` on a string or a template literal is text truncation, not a list cap | X | X | | | | | X | | | |
| 27 | A lens with a repeatable shape becomes a GENERIC prover over a roster, not N hand probes: cross-hive read / write-authz (psql generators), the fourth state / systemic ripple (abort every data read / every shared script, require a visible message and no stuck skeleton), hand-off (follow the first internal link, identity keys + hive name survive, then back) — each locks a dozen rows per run and its first run over a new roster finds real defects (four wrong founder counts, sticky headers under the notch, a 3 px nav overflow) | X | X | | | X | X | X | X | | |
| 28 | A gate's PASS over a roster is not evidence for a page it lists as silent/n-a — the log-tags gate passed while naming agentic-rag as having no emitters, and I locked its row on that vacuous truth before regressing it; a lock needs the gate to have exercised the page's property, and 'n/a' is a reason to record, never a green to spend | X | | | | | | | X | | |
| 29 | With every read aborted from the first byte, 13 of 21 DB pages showed no failure: skeletons and "Computing…" texts frozen past the retry envelope, "Live" chips over reads that never arrived, a maturity gate locking a surface because its readiness READ failed — the central transport-failure helper now settles stuck loaders into the shared error card, rewrites frozen progress texts, marks "Live" chips read-failed, and the maturity gate fails OPEN with the reason; a notice above a pulsing skeleton is two contradictory claims | X | X | X | X | | | | X | X | |
| 30 | A static extractor that lists query windows beside window phrases produces PAIRINGS, not findings — I relabelled logbook's entry-form field "Production this shift" as "Production today" because a since-midnight query sat elsewhere in the file; walk from the query's result to the element it paints before changing copy, and let a live prover that cannot find the label tell you the pairing was fiction | X | X | | | | | | | X | X |
| 31 | hive and community listened on nine realtime channels with NO backfill (`rtConn()` handed straight to `.subscribe()`, no `online` listener): rows written during a drop never arrived and nothing re-read on rejoin — a listening page needs a drop-aware subscribe handler that re-reads on the first re-SUBSCRIBED (debounced across channels) and on `online`; a polling page is covered only if its tick is short (60 s) | X | X | | | | | | | | |
| 32 | A `.limit(20)` read annotated `cap-ok: rows only` still fed a BADGE (`rows.length`) — the annotation must name every consumer of the rows, and a badge derived from a capped read is a count claim: `{ count: 'exact' }` or `N+` | X | X | | | | | X | | | |
| 33 | A `position:fixed` notice has no `offsetParent`: the degradation prover graded nine pages that HAD said so as silent; a prover's visibility predicate is part of its oracle — `checkVisibility()`, and a probe that dumps position/rect before the verdict is trusted | X | X | | | | | | X | | |
| 34 | Two provers walked the seller profile with `?seller=` where the page reads `?worker=`, and the SW prover navigated signed out and read six correct sign-in bounces as the landing shell — verify the instrument's query key and session before grading the page (a paramless / signed-out walk is a different page) | X | | | | | | | X | | |
| 35 | A one-shot "settle" fired 3 s after the first failed fetch, before the renders that paint the elements it settles had run (they complete after the ~9 s retry envelope) — the cure that runs too EARLY; schedule an idempotent settle at several points past the envelope, or hook it to the writer, and let a probe (notice present / settle absent) explain the gate's "silent" | X | X | X | | | | | | | |
| 36 | "No table with rows in >= 2 hives" is missing DATA, not a ceiling: an idempotent second-hive seeder (marker text, explicit ids, source timestamps kept, a tenant-column override for views keyed by `id`, auth_uid stamped from membership) turned sixteen n/a rows into nine locked recipes in one pass — reseed before you record n/a | X | | | | X | X | X | X | | |
| 37 | A polled/realtime feed rebuilt via innerHTML destroys the focused control and drops a keyboard user to `<body>` every tick (alert-hub 60 s, hive refetch) — remember the focused control's signature (tag + label + position among twins) before the rebuild and restore it after the synchronous render; prove it by holding focus across the REAL tick, not a hand-called render that a closure may hide | X | X | | X | | | | | X | |
| 38 | A best-effort helper with several independent passes under ONE try/catch fails as a unit: the first pass that throws (the skeleton pass, only on the page that had a skeleton) silently cancels every later pass — isolate each pass, order the cheap ones first, and expose a completed-pass counter a probe can read | X | X | | | | | | | | |
| 39 | Nine live provers each carried their own copy of the same preamble (sign-in, identity keys, visibility test, query keys, psql truths) and each copy grew a different blind spot — one shared harness (`tools/prover_harness.mjs`) owns the calibrations, provers import it, and a calibration fixed once is fixed everywhere; wire one prover at a time and re-run it, never while a chain is executing it | X | | | | | | X | X | | |
| 40 | A page whose renderers retry and REPAINT their placeholders after every failed attempt overwrites any settle scheduled at a fixed time (hive: 146 reads, 20 passes completed, placeholders back at 17 s) — a central 'say it failed' must re-apply on every repaint while the failure lasts (MutationObserver, debounced, bounded, disconnected on the first success), or hook the renderers themselves | X | X | X | | | | | | | |
| 41 | The same visibility blind spot lived in the PRODUCT's helper as in the provers: the central settle skipped every element whose offsetParent was null, which on hive was exactly the visible placeholders it existed to fix (44 passes, nothing changed) — a visibility predicate belongs in one shared place (`checkVisibility`, offsetParent only as a fallback), and `innerText` of a hidden container is '' (read `textContent` when a panel may be collapsed) | X | X | | X | | | | | | |
| 42 | A helper assigned with `var` a few lines above the function that calls it is undefined when that function runs first (the page's loader fires before the assignment) — declare page helpers as hoisted functions; and a prover's n/a for a control that existed on the previous run is a regression signal: capture page errors and fail, never n/a, when the page threw | X | X | | | | | | | | |
| 43 | A `` written through a heredoc can land as a literal backspace byte: two such bytes in utils.js's settle regexes made the settle a no-op on every page while four rewrites chased timing and visibility — after any escape-sensitive rewrite, assert the file has no control bytes; when a function runs but changes nothing, print its regex source from inside the runtime first | X | X | | | | | | X | | |
| 44 | A shared component must own its surface: the KPI tile set RAG colours but painted its button with no background, so any page without a button reset showed the browser's grey under pale text (Lc 0) — paint background/border/ink inline on the component itself | X | X | | | | | | | X | |
| 45 | A script-light public page still needs the platform's i18n MECHANISM (same language key, `_t`, `[data-i]` swap) or the worker's toggle does nothing there; keep article titles/blurbs as content (`card-title`) and key only the chrome | X | X | | X | | | | | X | |
| 46 | Close critique findings per finding against the page's CURRENT sweep, never in bulk: a row closes only when every finding is clean; record kind calibrations (reference/console) in the rubric with the reason and keep the un-graded signal (label coverage) in the note | X | | | | | | | X | | |
| 47 | A layout shift whose listed sources have identical y/height before and after moved HORIZONTALLY: the vertical scrollbar appearing as content grows shifts the whole page; reserve it once (`scrollbar-gutter: stable` on the root) before blaming any element or animation | X | X | X | X | | | | | | |
| 48 | A one-shot `[data-i]` swap at DOMContentLoaded misses everything rendered later; when the toggle is on, re-apply on DOM growth (debounced observer) and key the JS templates, or the worker's language works only for static chrome | X | X | | | | | | | | |
| 49 | Serial is necessary, not sufficient, on the 8 GB host: twelve serial page-set sweeps plus provers in one night left the WSL engine without headroom (REST timeouts, `docker info` 500, 1.2 GB free) — check free memory before every chain, keep page sets ≤ 8, pause under ~2 GB, kill a timed-out run explicitly; recovery is restart Docker Desktop, start the exited containers, re-verify one page | X | | X | | | | | X | | |
| 50 | Stopping a background task stops the harness's handle, not the process tree: the script, its node runner and its headless browser live on and contend with the next run — after any stop, kill by command line (excluding your own shell's PID) and verify no runner or headless browser remains; and a monitor must name its file, never `ls -t` | X | | X | | | | | X | | |

| 51 | The rubric's OWN `vis` helper tested `offsetParent === null` - the third home of the fixed/sticky blind spot (after two provers): a primary button in a sticky bar and the hub FAB read invisible, so A1 scored cta=0 and W2 nav-hub=false on real pages. `checkVisibility({opacityProperty,visibilityProperty})` + a zero-rect guard; audit every visibility helper in an instrument, not only the newest one. | X | X |  | X |  |  |  |  | X |  |
| 52 | A padded button is TALL without wrapping: `rect.height / lineHeight` read 'Save' as 2 lines. Count LINE BOXES - a `Range` over the element's contents, distinct `getClientRects()` tops - before calling a label wrapped. | X | X |  | X |  |  |  |  |  |  |
| 53 | A right-anchored menu at a fixed width fits only while its button sits far enough right; a wrapped header on a phone puts the button at the LEFT edge and the menu off-screen (hive More). After opening, measure and clamp inside the viewport (re-anchor left/right, >=8px margin) - a menu's position is a runtime decision, not a CSS constant. | X | X |  | X |  |  |  |  | X |  |
| 54 | The wayfinding crumb stripped '· | X | X |  | X |  |  |  |  |  |  |
| 55 | A runtime-injected scrollbar restyle (nav-hub's `::-webkit-scrollbar{width:6px}`) SHRANK the reserved gutter 15->6px ~340ms after first paint: the centred column moved 4.5px on every load = a 0.07 CLS with 'div' as its source. Scrollbar geometry belongs PRE-PAINT (tokens.css in <head>); `scrollbar-gutter:stable` reserves whatever width the bar has AT THAT MOMENT. | X | X | X |  |  |  |  |  |  |  |
| 56 | A harness identity with no saved state walks the FIRST-RUN path: the Baguio hive had no `hives.intent`, so hive.html opened a full-screen intent modal on every load - the hub read hidden (W2), More was untappable, and every hive measurement was of the onboarding state. Seed the mature state for the harness actor, and let a prover SAY which state it measured. | X | X |  |  |  | X |  |  |  |  |
| 57 | A diagnostic that MIRRORS a grader must mirror ALL its checks: b3_diagnostic reported integrations '(clean now)' while the rubric still failed passive=2 - it mirrored long+grade only. Read the grader's own offender dump (`b3_offenders` in the page json) before rewriting copy. | X |  |  |  |  |  |  |  |  |  |

| 58 | The tool transport turns a doubled backslash into a single one inside a heredoc, so the FIX for a stray backspace byte (`'\b'`) arrived as another backspace and the replacement was an identity (size unchanged, count unchanged). Build such bytes from code points (`bytes([92, 98])`) and prove the write by SIZE and a read-back count, never by the script's own print. | X |  |  |  |  |  |  | X |  |  |
| 59 | A six-pixel overshoot past a parent with `margin-right:-6px` is optical alignment, not a spill; a spill lens must subtract designed negative margins (and read the grandparent) before reporting. | X | X |  |  |  |  |  |  | X |  |
| 60 | The sweep actor's OWN state decides what the sweep measures: Pablo's two hives had no `hives.intent`, so hive.html opened its full-screen intent modal at every sweep load, nav-hub hid the hub behind the dialog, and W2 read nav-hub=false for weeks while the harness worker's hive (seeded earlier today) passed. Seed the mature state on EVERY actor's hive, and let a failing dim name the STATE it measured in. | X | X |  |  |  | X |  |  |  |  |
| 61 | Generalise a shared rule by SUFFIX only where the suffix is a type: `[class$="-pill"]` is safe (a pill is one line by definition; header-pill broke 'Read-only' at its hyphen), `*-chip` is not (wh-source-chip is a sentence). Check every use of a class before a shared rule lands, and let the outside/spill lens re-measure right after. | X | X |  | X |  |  |  |  | X |  |

| 62 | Correcting a SHARED visibility helper changes every lens downstream: once fixed/absolute elements became visible, R4 counted engineering-design's decorative .aurora-bg (800px, no text) and an empty 26px toast host as orphan voids and two 100% pages read 98%. When a shared helper changes, re-run every lens that consumes it and audit each lens's own exclusions (decoration, live-region hosts) in the same change. | X | X |  |  |  |  |  |  | X |  |
| 63 | An aria-live host (`#toast role=alert`, 30 pages) must collapse to zero height when empty, never `display:none` - a live region has to exist in the tree BEFORE its first message or screen readers miss the announcement. `#toast:empty{height:0;padding:0;overflow:hidden}` in tokens.css. | X | X |  | X |  |  |  |  |  |  |
| 64 | A control is a LABEL or it is PROSE: a tile button carrying a title plus a standard citation ('Availability % ISO 14224:2016 §9.2') may break the citation at a space by design; only a short-label control (<=4 words) is judged by its descendants' line count. The rubric's own R4/A1 read the same way: a disabled primary until inputs exist is honest UX, not a missing CTA. | X | X |  | X |  |  |  |  | X |  |

| 65 | Reproduce a sweep finding under the sweep's OWN identity before blaming the instrument: R3 read two card treatments for weeks because the sweep actor (Pablo) gets a fourth JS-rendered card with inline padding the harness worker never sees; three probes as the harness worker 'proved' one treatment. probe_eval --as <actor> --vw <sweep viewport> is the reproduction, and a JS-rendered card must reuse the class's padding, never an inline value. | X | X |  |  |  | X |  |  | X |  |

| 66 | A SUBSTRING attribute selector is a false friend on a Tailwind page: `[class*="item"]` matches `items-center`, `[class*="row"]` matches `flex-row`/`grow`. Any lens that asks "is this control inside a row/card/item?" must match class WORDS (a regex with separators), or it silently reclassifies every flex button. | X | X |  |  |  |  |  |  | X |  |
| 67 | Collecting candidates through several selectors and then counting occurrences counts ELEMENTS TWICE: A1's lone 'Add Part' primary arrived via [class*=primary], the filled-button pass and headerCtas, so the repeated-row-action filter dropped it and five pages read cta=0 for weeks. Dedupe by element BEFORE any frequency test. | X | X |  |  |  |  |  |  |  | X |
| 68 | A long PROSE label pinned with `white-space: nowrap` becomes its container's min-content width: it spilled design-system's adoption row at 360 and, when I added the same rule to `.wh-source-chip`, laid two whole pages out 1067px / 802px wide. nowrap belongs on short labels (pills, buttons, counts), never on a sentence. | X | X |  | X |  |  |  |  | X |  |

| 69 | The platform's 60 PUBLIC calculator pages (its whole SEO surface) sat at 77-80% while the generator that emits them already carried every fix: the deployed copies predate the generator and only a PROMOTION (staging -> /tools/, the owner's gate) moves them. Measure BOTH sides before calling a page bad - deployed 79%, staged 100% - and treat 'the generator is ahead of the deployment' as its own class of finding. | X | X |  |  |  |  |  | X |  |  |
| 70 | A2's 'blocks' and C3's 'grouped regions' both count elements that have an EDGE (border/background/shadow) plus >=6px padding plus text: a long prose column scores 0 no matter how good its headings are. One CSS rule making each <section> a card fixed both dims on 60 pages - and the section margin has to sit on the 8-pt scale or R1 flags it (28px -> 24px). | X | X |  |  |  |  |  |  | X |  |
| 71 | LLM prose belongs behind `data-ai-generated`, which the copy lenses skip: shift-brain's shift brief and hive's pattern alerts both failed B3 on sentences no human wrote. Grade generated text with the AI-output gates, and mark its HOST so the static-copy lens grades only static copy. | X | X |  |  |  |  |  |  |  |  |

| 72 | An edge function has no page, but it SPEAKS: every error string a client renders verbatim is copy, and grading it (readability, a next step, no leak) turned 38 permanently-pending rows into measurable ones. When a lens cannot reach a surface, build the lens that can rather than accepting 'covered by nature'. | X |  |  |  | X |  |  | X |  |  |
| 73 | Eight functions named the missing SECRET in the response ('set RESEND_API_KEY in secrets') and six returned the raw exception ('error: (err as Error).message'). The operator detail belongs in console.error; the reply gets a sentence a worker can act on. Both are information disclosure AND bad copy. | X |  |  |  | X |  |  | X |  |  |
| 74 | A copy grader invents defects unless it is calibrated against the code's own idioms: a ternary ('err instanceof Error ? err.message : String(err)') is not a reply, `tenancy.message` is curated copy from a shared guard, `errJson(error: string)` names a parameter, an ops summary is not a failure, and a machine code paired with a human message is not prose. Anchor the pattern to real object keys inside real client responses. | X |  |  |  |  |  |  | X |  |  |

| 75 | Run the gate suite BEFORE calling a session's work done: 287 gates found ten reds, seven of them introduced by the session itself (action-links, empty catches, em dashes, a table name on the glass, raw brand hexes, an un-re-mined registry, clone growth). A day of page fixes is not verified by the page sweep alone. | X |  |  |  |  |  |  | X |  |  |
| 76 | A var() FALLBACK hides a missing token: `var(--wh-amber-text, #f7a21b)` rendered the raw hex forever because `--wh-amber-text` was never defined. Grep the token you are falling back to - if it does not exist, the fallback IS the value. | X | X |  |  |  |  |  |  | X |  |
| 77 | A risk score keyed by free text can name an asset that does not exist: batch-risk-scoring reads the logbook's `machine` field, so ops-home could headline 'CRITICAL RISK: CP-01' and open onto nothing. Any score/alert derived from typed text must resolve against the registry (name OR tag, normalised) before it is written. | X |  |  |  |  |  | X |  |  | X |
| 78 | A forward-only ratchet over a SIMILARITY detector moves when unrelated pages are standardised: adding the shared head block to 8 pages 'grew' a 661-line clone whose inline JS did not change (183 -> 183). Prove growth against the real content before extracting or re-baselining, and write the reason into the baseline. | X | X |  |  |  |  |  | X |  |  |

_Row 17 folds the former row 22 (same lesson, two rosters). Multitenant rows 1 and 8 carry the tenant angle (identity resolution; RLS-preserving rollups). Data Engineer rows 8, 16, 17 carry the query/gate angle. Analytics Engineer row 8 carries the metric-definition angle (MAU = identified viewers)._

**On approval:** each X becomes one dated bullet in `C:/Users/ILBeronio/.claude/skills/<skill>/SKILL.md`, written from that skill's angle in one pass.

## Addendum — 2026-09-06 live-walk wave (3 lessons, 9 skill targets)

| Lesson | DevOps | Security | QA | Data Eng | Multitenant | Performance | SEO/Content |
|---|---|---|---|---|---|---|---|
| The repo's deploy config was for the WRONG platform: `_headers` (Cloudflare) + `netlify.toml` (Netlify) while the site runs on Vercel — zero security headers in prod, `/_fixtures/*` served 200. Identify the host from the response before trusting any platform file; assert every promise against the deployed origin. | X | X | X | | | X | X |
| A refusal cannot be proven by a reader who is allowed to read: the postgres MCP connects as the table OWNER with `rolbypassrls` (reported 944 foreign rows visible), and the harness's default persona is a `marketplace_platform_admins` member (seven false cross-hive leaks). Choose the persona for the LENS; use PostgREST with a real user token. | | X | X | X | X | | |
| A tile-vs-canonical gate must pair each number with the query BY HAND: three of four first mismatches were the prover's query, not the page (`wo_state` null on every row; "low" means low+critical; "healthy" is the MIDDLE band excluding surplus). A heuristic pairing is a second implementation of the product. | | | X | X | | | |

### Addendum 2 — 2026-09-06, later in the same wave (5 more lessons)

| Lesson | DevOps | Security | QA | Frontend | Performance | Mobile | Realtime | Analytics | Designer |
|---|---|---|---|---|---|---|---|---|---|
| **Measured and never kept**: the envelope computed `latency_ms` on every response and persisted none, so the SLO board's first golden signal had no producer. And an IMPORT is not adoption — 17 edge functions import the logger and never call it. Run each dashboard panel's own query against its own datasource. | X | | X | | X | | | X | |
| **The lens can be wrong, not just the code**: 58 rows asked whether calculator pages "compute standalone"; they contain no form at all. The real defect was the hand-off — 60 CTAs named a calculator and linked to a page that read no parameter. When a prover returns an impossible result on EVERY subject, question the lens before adjusting the instrument. | | | X | X | | | | | X |
| **A guard is only proven by trying the door**: a static scan finds a confirm in the code, not on the path the button takes. Clicking found eleven guarded controls reading as unguarded — a real mouse click is INTERCEPTED by whatever is on screen and Playwright's refusal is silent. Dispatch in page; and a surface where nothing came on screen is NOT REACHED, never "nothing destructive here". | | X | X | X | | | | | |
| **`checkVisibility()` ignores `visibility:hidden` and opacity by default**, and says nothing about a sheet parked off-page by a transform. Right for a rendering lens, wrong for "can a person reach this" — ask for the properties explicitly in any keyboard, tap-target or interaction lens. | | | X | X | | X | | | X |
| **A shell file changed means `CACHE_NAME` must move**: editing nav-hub.js without bumping the service-worker cache leaves every installed user on the old shell. Bump in the same edit and say what changed. | X | | X | | X | X | X | | |


### Addendum 3 — 2026-09-07, the journey-cluster wave (9 lessons, still awaiting your one-pass approval)

Eleven journey clusters walked; eight real defects fixed; the instrument wrong twenty times. The cross-skill
table below is what I would write, on your word.

| Lesson | QA | Frontend | Security | DevOps | Performance | Mobile | Designer | Architect | Data Eng | Analytics | Knowledge Mgr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A right that nothing invokes is not a right.** `export-hive-data` shipped for months with no page calling it, and `deactivate_my_account()` existed only on the landing page. Before concluding a capability is MISSING, search for the JOB, not your name for it — the platform's word was *deactivate*, and searching for "delete" nearly shipped a weaker duplicate: a table, a migration, an RLS policy and a cap, for a right already implemented better. **The bigger the thing a gap justifies building, the more certain you must be it does not exist.** | X | X | X |  |  |  |  | X | X |  | X |
| **A source-reading gate constrains how the source may be written.** A comment pushed a function body past an 800-char scan window; moving it out made the comment match the gate's own regex; a different gate then read an English sentence as a property access, and caught two successive comments *about* that. Describe what a gate looks for; never reproduce it, never quote what tripped it. | X | X |  | X |  |  |  |  |  |  | X |
| **A `` written through a shell heredoc becomes a literal backspace byte**, and the regex then hunts a control character no file contains — failing *plausibly*. Five more instances this wave; one cost three wrong theories before I checked the bytes. When a regex disagrees with the same regex run elsewhere, compare the BYTES before the logic. | X | X |  | X |  |  |  |  |  |  | X |
| **An impossibly clean number is the probe, not the product.** "29 pages state what the platform is worth" was the word *saved* in every save toast (real answer: 3). "Zero timers repaint" was a pattern that had stopped looking. Distrust a result that is too good in EITHER direction. | X |  |  |  | X |  |  |  |  | X | X |
| **`en-PH` is a format, not a clock.** `toLocaleDateString("en-PH", …)` with no `timeZone` renders in the runtime's zone — UTC on Supabase Edge — so every report subject read eight hours early under a Philippine label. `toISOString().slice(0,10)` has the same bug in date form: for a third of every local day it names yesterday. | X |  |  | X |  |  |  |  | X | X |  |
| **Sign-out that clears a hand-kept list leaks whatever was added later.** Nine such lists had drifted apart; none could name `wh_hive_lastseen_<hiveId>`, one key per hive. Sweep identity by PREFIX, and never on a shared device leave the last person behind. | X | X | X |  |  | X |  |  |  |  |  |
| **Consent must be declared before the config, not after the tag.** Consent Mode defaults to denied on the first line; a banner shown after collection begins is asking permission for something already done. A stored answer must be replayed before config or a reload silently re-collects. | X | X | X |  |  |  | X |  |  | X |  |
| **A landmark or a guide may be INJECTED rather than written**, so a static read of page source reports absence where a visitor sees one. Check what the shared chrome renders before counting a page as missing anything. | X | X |  |  |  |  | X |  |  |  |  |
| **Prove an action by the trail it leaves, not by the DOM shrinking.** The approval walk's real evidence was `hive_audit_log` moving 19 → 21 with actor and target — the same record a later dispute is settled from. | X |  | X |  |  |  |  | X | X |  |  |

### Addendum 4 — 2026-09-07, the Tagalog-first and AI-trust waves (6 lessons, awaiting your one-pass approval)

| Lesson | QA | Frontend | Security | DevOps | Performance | Mobile | Designer | Architect | Data Eng | Analytics | Knowledge Mgr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A healthy page shows neither its failure copy nor most of its buttons.** The Tagalog census (sentences, empties, controls not through `_t()`/`data-i`) was driven to zero and the live walk still read achievements 7%, observability 3%, architecture 0% — what a person reads on a working page is headings, labels, paragraphs, table heads, options. When a prover has a live verdict and a static proxy, read the live number FIRST; the proxy only locates work. The structure that answered it: `tools/i18n_page_dict.py` + `i18n/<page>.json` (visible text → authored Taglish) tagging elements `data-i="p_…"` and emitting `WH_FIL_PAGE_VISIBLE`. | X | X | | | | | X | | | | X |
| **Before emitting into any `window.X`, grep who else assigns X.** The first dictionary block set `window.WH_FIL_PAGE = {…}` and 26 pages reassigned that name later in the document — a live probe found 6 keys where 39 were emitted. A shared global name is a write race; the fix was a separate global merged by the applier (common → visible → page). | X | X | | | | | | X | | | |
| **A one-shot DOM swap loses to a page that renders from data after DOMContentLoaded.** architecture.html re-draws its map from a model after load, so 46 tagged elements read 1 translated. The applier now runs at DOMContentLoaded, at load, and on a debounced MutationObserver — the same shape utils.js already used for late-rendered controls. | X | X | | | | X | | | | | |
| **Strings a person never reads are not sentences.** The census counted `console.warn('… failed:')` inside `.catch` (not at line start), selector strings (`#read-failed-state p.text-xs`), thrown Error text and `${escHtml(name)}` painted into a button — and a trailing `// don't` comment's apostrophe opened a fake string that hid eleven real sentences on community.html. Strip console calls wherever they sit, strip selector lookups, strip trailing comments, and treat interpolation as data. | X | X | | | | | | | | | X |
| **A shell heredoc mangles backslashes in this harness — twice more today.** `\\.` became `\.` (regex broke), `\\n` became a real newline inside a Python string (SyntaxError), `\\b` became a backspace byte. Any script that carries a backslash goes through the Write tool to a file, never through an inline heredoc. | X | | | X | | | | | X | | |
| **Every AI answer a person acts on needs the same three things, so build them once.** Only the Assistant chat and the launcher had 👍/👎; Asset Brain, the shift briefing, the analytics narrative, the resume polish and the voice journal showed answers with no way to be heard and no source. `whAiTrustRow(container, {db, agent, source, page, question, answer, groundedOn})` in utils.js renders the source chip + the rating row writing `ai_reply_feedback` (best-effort, the CONTROL reflects whether the write landed), and the prover learns the shared contract instead of each page's copy. | X | X | | | | | X | X | | | |

### Addendum 5 — 2026-09-07, the recovery-path wave (5 lessons, awaiting your one-pass approval)

| Lesson | QA | Frontend | Security | DevOps | Performance | Mobile | Designer | Architect | Data Eng | Analytics | Knowledge Mgr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A "press every X" sweep reaches nothing; a rostered control is reached the way its person reaches it.** The generic label sweep reached 0 of 53 destructive controls — they live behind a menu, a modal, a tab, a 360 view, a wizard three "Next" presses deep. The prover now carries an authored path per control (`steps` → `trigger` → the roster heads it answers), read from each page's call sites, with `text=` steps for wordy openers and `js:` steps for a page's own opener. | X | X | X | | | | | X | | | X |
| **A gate that reached nothing must not pass.** "PASS recovery-path - 0/0 reached" with 53 controls NOT REACHED was a vacuous green; an unreached control is owed and fails the gate. Any gate whose denominator can be zero must fail on the owed count, never on `bad` alone. | X | | X | X | | | | | | | |
| **Count before and after with the same eyes.** The confirm-detection counted every dialog in the DOM before a press and only visible ones after, so a real overlay never out-counted the hidden sheets and every confirm read "fired with no confirm — simply gone". A delta oracle computes both readings with one function; when a gate says a control did nothing, press it by hand in a probe before touching the product. | X | X | | | | | | X | | | |
| **Twelve controls exist only when a row does — seed with prep and cleanup, in the page's own vocabulary.** Each such entry inserts one row for the harness worker (confirmed by RETURNING id) and deletes it on every exit path. Every wrong guess was one constraint away: schedule_items wants the Manila day as TEXT and status `pending`; service_requests.mode is `instant|quote`; the objection button waits for `completed`; the duplicate-hail guard matches catalog item + address + `broadcasting`; the import history filters `operation='file_import'`; a change order needs a project whose type shows the pane. | X | | X | | | | | X | X | | |
| **State leaks between paths: start every path from a fresh page, close a confirm by its own Cancel, never press a proven head twice, and treat a step as an opener.** The pre-click sweep folded a contacts list; removing an overlay left the next path mid-confirm; the second press of alert-hub's Reject met an open confirm and overwrote the good verdict; marketplace-admin's queue tab was "invisible" at 1280 yet still switched its panel when pressed. And where the undo IS the way back (the vehicle wizard), accept the confirm and prove it by the census returning to its pre-wizard rows. | X | X | X | | | | | | | | |

### Addendum 6 — 2026-09-07, the fast suite at the RV milestone (2 lessons, awaiting your one-pass approval)

| Lesson | QA | Frontend | Security | DevOps | Performance | Data Eng | Multitenant | Architect | Knowledge Mgr |
|---|---|---|---|---|---|---|---|---|---|
| **A wrapper a wave adds is a wrapper every gate must read through.** The Tagalog-first wave wrapped confirms in `_t(en, fil)` and tagged visible elements with `data-i`; four gates then reported defects in a product that had not changed (the destructive roster read two confirms as LOST and shrank; the T31 placeholder regex required `value=""` first; the AI-7 window was 5 chars short; a string `.slice(0, 4000)` read as a capped list). When a wave changes the SHAPE of source, grep the gate roster for the old shape before the suite runs and teach each instrument to read through the wrapper - the English head stays the key. And carry regex fixes in a file written whole, never a bash heredoc: `` arrived as a backspace byte. | X | X | X | X | | | | | X |
| **A stranger's read dies on a column it never asked for.** RLS predicates and `security_invoker` views run as the CALLER: revoking anon on `marketplace_listings` broke the seller policy's `EXISTS` subquery on that table, and `v_marketplace_sellers_truth` naming column-revoked fields refused a stranger's whole read (the marketplace seller card had been dark since 2026-08-03). Before a REVOKE, grep policies and invoker views for the table; put a caller-blind predicate behind a one-boolean SECURITY DEFINER helper; give the stranger a definer view with masks (`case when auth.uid() is not null then col end`), read-only asserted, anchored under its own canonical domain; never fire a read you know is refused - say "sign in" instead of painting a zero from a 401. Lock with a recipe over EVERY hive-scoped table, which is what caught it. | X | X | X | | | X | X | X | |
| **The same number on 24 pages was one page.** Every deep-link row read exactly 14,386 characters because every app page bounces a cold visitor to the sign-in landing page, and the lens (an h1 exists, ≥300 characters) passed on the door 24 times. An identical reading across different subjects is the instrument describing itself; an arrival lens must bind to the DESTINATION's own words (its title, its nav label) on the page or on the door, and require `?return=` to carry the page. The product half: the door now says "Sign in to open <Label>" from the nav's own vocabulary. | X | X | | | | X | X | | X |
| **A reader who never acts meets no expiry.** The expiry-mid-read lens cleared the session, routed 401s, waited 20 s and read "noticed but no way back" on 23 pages - measured, the page made ZERO requests while a person only read, and the "notice" was the source chip (`role="status"`). A failure that surfaces on an action is measured at the person's next action (coming back: the door with return, the shared notice with its Sign in button), and provenance chrome is excluded from every notice pool. | X | X | X | | | | | | X |
| **Ask before you judge the refusal.** The quota-spent cell graded a page it had never asked anything, so nothing could be refused; the AI-trust wave's ask mechanics (open, prepare, type, send, or the page's own trigger) now live in one module, `tools/ai_ask.mjs`, shared by both provers, and view-only surfaces are graded on surviving. A lens whose subject only speaks when spoken to must speak first. | X | | | | | | | X | X |
| **Shared chrome is graded once, and a lens must know which half a person can reach.** The page-floor walk counted the nav-hub's and feedback panel's buttons as the page's own bare buttons and typed its draft into the companion's ask box; the a11y walk counted the hidden hub drawer's 26 buttons as nameless and its tile dot as colour-only, and keyed a focus trap by class so nine chips in a row read as one. Per-page lenses exclude chrome with the survey's own selector list; accessibility lenses read only what is reachable (`visibility`, `aria-hidden`), name from `textContent`, and key focus by row and column. | X | X | | | | | | X | X |
| **A stylesheet injected after first paint is a layout shift on every page.** utils.js restyled the shared `.wh-help` block after paint with values that differed from components.css (voice-journal's summary 24 → 55px); five real CLS findings at 390 were this plus late-filled chips, wrapping tab strips and a chip appended after the toolbar. Ship shared CSS statically; reserve phone heights for late-filled lines; measure CLS at the walk's viewport with sources and first-frame rects. | X | X | | | X | | X | | |
| **A closed off-canvas panel still widens the page.** The feedback panel, `translateX(100%)` and `visibility:hidden`, extended every learn article's scroll width by 93px at 390; `width:0` was not enough while its children stayed in layout. Closed shared chrome is an EMPTY box; a widget never relies on the host's `overflow-x:hidden`. | X | X | | | | | | X | |
| **A shape change owes its ledgers a regeneration and its oracles a lesson before the suite.** The wave-2 close suite spent six reds reporting the day's own work back: a new view the canonical registry did not know, a prover library mined as two product AI seams, a boundary oracle bound to a table anon can no longer read, clone adjacency after a moved block, a raw hex and a non-total order. After adding a view / moving a block / adding a library / revoking a grant, run the registry miner, the roster builder, the seam miner and the clone baseline, and re-read the oracles that assert the old shape, BEFORE `--fast`. | X | | X | X | | X | | X | X |
| **A deploy-gated claim still owes its local half.** 38 rows sat at fixing behind "only Ian's deploy can make the claim true"; a 90-line local server applying vercel.json's own header rules the way the Vercel edge merges them (every matching rule in order, later keys win) walked all of them - and found the `/sw.js` no-store rule listed before the generic js/css rule, which would have shipped the service worker cached for an hour. Before parking a row behind a deploy, name the artifact the deploy ships and build the smallest local runtime that applies it as the platform will; the row reaches locking, the deploy stays the lock. The same move closed the last five instrument rows (CDP is the devtools instrument, Mailpit is the outbox, the credit gates run as the buyer are the hostile persona). | X | | | X | X | | | X | X |

## Addendum — 2026-09-07 expansion wave 3, the full-journey instrument (5 lessons, 6 skill targets)

Wave 3 seeded 1,502 rows (2,437 -> 3,939 in scope; the headline dropped to 61.9% the same day) and its
largest direction, W3-JN, walks 724 WHOLE journeys. The instrument's first run reported six failures out of
six and **not one was the product** - so every lesson below is about how a journey oracle lies.

| Lesson | QA | Frontend | Performance | Security | DevOps | Knowledge Mgr |
|---|---|---|---|---|---|---|
| **A closed drawer is not an absent one.** The nav hub is `visibility:hidden` until opened, so a visibility filter across the page read "no way onward at all" on every hop of every journey. Count a shared-chrome link whether or not its drawer is open; require visibility only of the page's OWN links. | X | X | | | | |
| **A thread read on a page you did not ask for is not that page's thread.** Three casts could not sign in, every step bounced to `index.html` - which links to everything - and the walk counted the landing page's links as five journey threads. A step that did not ARRIVE (landed == requested) contributes no evidence about the page it was supposed to be. | X | X | | | | |
| **A page under a render floor is UNREADABLE, not "leads nowhere".** With a second job running on an 8GB host, alert-hub read 658 characters and 0 onward links; alone, 4,953 and 27 - same page, same hive. Steps thinner than a floor must be reported unreadable and excluded from the verdict, and heavy jobs must run one at a time. | X | X | X | | X | |
| **An unreadable answer is not a zero.** Under load the docker API returns 500; a helper that swallows that into `''` prints "this hive has nothing" - a finding about the probe wearing the product's clothes. Retry, then report UNREADABLE, and make every caller handle it. | X | | | | X | |
| **Anchor every short acronym in a routing map.** `INP` matched inside "input" and sent sixty calculator rows about naming a standard to the performance profiler - the same shape as `SLO` matching inside "slower". A routing table keyed on three-letter tokens needs `\b` on every one of them. | X | | X | | | X |

**Also proposed:** a cast that cannot sign in is a SETUP finding said once, never six bounced pages reported
as product failures; and when a fixture has no recoverable credential, give it the project's local test
credential rather than spoofing a session - a walk that fakes its identity proves nothing.

**Two more from the same instrument, both caught before anything was banked:**

| Lesson | QA | Frontend | Performance | Security | Knowledge Mgr |
|---|---|---|---|---|---|
| **Stable text is not settled - a page is still working while it is still asking.** `pm-scheduler.html` read 493 characters in every hive on every run; opened alone with a longer wait it renders 2,617. It paints its shell in under a second, holds still while its list is in flight, then fills - so a reader that waits for "the text stopped changing" leaves mid-question and calls the page near-empty. Require no REST/RPC read in flight, and none for ~1.2s, before believing a reading. | X | X | X | | |
| **Reproducibility proves the READER is consistent, never that the reading is true.** "The same 493 characters in every hive on every run" was used as evidence it must be the page - which is exactly what a systematically early reader produces. A number that repeats is a hypothesis, not a finding; confirm it by a DIFFERENT route before writing it up. | X | | | | X |
| **A cleared value is not a missing reading.** The identity check passed any step whose hive key was EMPTY (`!hive || hive === expected`) - and empty is precisely the state a page leaves behind when it revokes a member and drops to solo scope. The one page that can throw a member out would have read as "identity kept". Compare against the expected value, never against "or nothing". | X | X | | X | |

**The wave's first PRODUCT defect, and what it teaches (2026-09-08):**

| Lesson | QA | Frontend | Multitenant | Community | Designer | Knowledge Mgr |
|---|---|---|---|---|---|---|
| **A default derived from identity, cached before identity is known, is wrong for ever.** `nav-hub` derived a display mode from `wh_hive_role` and persisted it; the first page anyone meets renders the hub signed OUT, so it stored `field` and preferred that value permanently. Every supervisor navigated with a worker's menu - 17 links, no Analytics, no Alert Hub, no Reports. Record WHY a default was stored (chosen / derived / guessed) and re-derive a guess when the identity arrives. | X | X | X | | | X |
| **A repair to a role-gated default needs teeth in BOTH directions.** Handing everyone the supervisor menu would be a worse defect than the one being fixed, so the gate asserts three things: a worker keeps the tight set, an explicit choice is never overwritten, and a supervisor gets their own surfaces back. | X | X | X | | | |
| **Some defects live only in the thread BETWEEN pages.** Every page involved works perfectly when reached by URL; 2,437 rows of per-page work could not see this, and one journey walk found it as "no way onward at all". When a page-level suite is green everywhere, the next class of defect is navigational: can a person GET from the page they are on to the page they need. | X | X | | X | X | X |

## Addendum — 2026-09-08, the content waves (4 lessons, 8 skill targets)

A night in which the instrument was wrong far more often than the product, including four times about a
single question. Nothing here is proposed as a skill edit until you approve it.

| # | Lesson | QA | Frontend | Performance | Mobile | Security | DevOps | Data Eng | Architect |
|---|---|---|---|---|---|---|---|---|---|
| 8.1 | When a pattern keeps being wrong, stop patterning — read the declared field | X | X | | | | | X | X |
| 8.2 | A correction is not landed until every instrument that asks that question has it | X | | | | X | X | | X |
| 8.3 | A lens must not report an outcome for a test it never ran | X | X | | X | | | | |
| 8.4 | A lock on one resource is not permission to fan out on another | X | | X | | | X | X | X |

**8.1 — stop patterning, read the declared field.** *"Do these 60 calculators cite something an engineer can
look up?"* was answered five times. Pass 1 said 60/60 because the pattern matched HTML **tag names**
(`<section a…`). Pass 2 said 11/60 by over-correcting into demanding the literal word *Table*. Pass 3 said
60/60 because bare two-letter families (`EN`, `UL`) with no word boundary matched inside
`min-height: 44px; padding: 12px` — **a CSS block on every page.** Pass 4 accused six correct pages because
the family-to-number window excluded periods, so `NSCP Vol.2` could never match. Pass 5 read the `standard`
field the generator declares and settled it. *For QA/Frontend:* a rendered page is a haystack; before writing
a regex over it, ask where the value is **declared** upstream. *For Data Engineering/Architect:* generated
artefacts have a source of truth, and asserting against the generator's input is deterministic in a way that
parsing its output never is. **Four corrections to one regex is the signal that the regex is the wrong
instrument.**

**8.2 — the twin instrument.** The static gate was corrected through all four passes while the browser lens
kept its own copy of the refuted pattern, and accused **forty** calculators of naming no clause while they
cited `ASHRAE 62.1` and `ISO 898-1:2013`. The fix was not two correct copies but **one answer**: the gate
publishes what each page owes its reader, the browser checks only whether the reader can see it. *For
Security/DevOps:* the same shape as a rule fixed in one policy and left stale in its sibling — when you
correct a check, grep for every other place that asks the same question. *For QA:* when two instruments
disagree, the disagreement is the finding, and the live read stands where the person stands.

**8.3 — a receipt for a test that never ran.** The range lens types `-999999` into every number field. On a
landing page there are none, so it typed nothing, found no refusal words, and wrote
`accepted a negative input silently`. The **verdict** was correct; the **sentence** was false — and the
sentence is the evidence a human reads later. Twenty rows were banked carrying it. The first guard I wrote
asked whether the page had *any* input while the pass types only into `input[type="number"]`, so a page whose
only field is a search box would have produced the same false sentence: **the guard must name the same thing
the test touches.** *For QA:* read the receipts of **passing** rows, not only failing ones — a green row with
a false basis is worse than a red one, because nobody returns to it.

**8.4 — one lock is not permission to fan out.** A shared browser lock made three concurrent waves look safe.
Nothing serialised the **database**: an 8 GB host went to 0.19 GB free and docker stopped answering, and four
of six journey chains came back "the database did not answer" about hives that are full of data. A saturated
host does not produce slow truth, it produces **confident fiction**. *For Performance/DevOps:* enumerate every
contended resource before parallelising, not just the obvious one. *For QA:* a "complete" that produced no
artefact is not complete — one batch exited 0, printed a finishing line and had written nothing. Also: the
serial driver I wrote to fix this had **no lock of its own** and a second copy was started beside the first —
a tool that serialises work must first serialise itself.

## Addendum — 2026-09-08, the bilingual defect and the writer (5 lessons, 9 skill targets)

| # | Lesson | QA | Frontend | Performance | Mobile | Security | Designer | Community | DevOps | Architect |
|---|---|---|---|---|---|---|---|---|---|---|
| 9.1 | A `typeof` guard around a global turns a missing file into silence | X | X | | | X | | | X | X |
| 9.2 | Grade the outcome a person gets, never the mechanism that should produce it | X | X | | | | X | X | | |
| 9.3 | Not every small control owes 44px — WCAG 2.5.8 exempts a link inline in a sentence | X | X | | X | | X | | | |
| 9.4 | A 404 and an empty page look identical until you read the status code | X | | | | | | | X | |
| 9.5 | An overhead that is right per call can be ruinous per wave | | | X | | | | | X | X |

**9.1 — the guard that hid the wire.** All 60 calculator pages end with
`if (typeof whI18nApply === 'function' && window.WH_LANG === 'fil') whI18nApply(window.WH_FIL_PAGE)`.
`whI18nApply` is defined only in `utils.js`, which **none of them loads**; `WH_LANG` is also set there. Both
halves were permanently false, with no error, no warning and no failing gate — a complete Filipino dictionary
shipped on the most public surface and reachable by nobody. *For Frontend/Security:* a `typeof` guard around
a platform global converts "this file was never loaded" from a loud `ReferenceError` into nothing; when you
write one, name the file that defines it and check this page loads it. *For Architect/DevOps:* only a check
that reads **both sides at once** — what a page calls and what a page loads — can see this, which is why it
is now a gate over all 191 pages. *And the fix is not always to load the dependency:* `utils.js` is 362 KB,
an app bundle on a static landing page paid for by every English reader; a 3.5 KB file defining the same
names was the right answer.

**9.2 — outcome, not mechanism.** The lens that graded bilingual support asked
`document.querySelector('[data-i]')` — a question about **attributes**, and attributes were exactly what was
present while translation was exactly what was missing. The replacement sets the language the way a person
sets it, loads the page twice, and checks the **words changed**. *For QA:* whenever a check asserts that a
mechanism is present, ask what a person would observe if the mechanism were present but broken, and assert
that instead. *For Designer/Community:* "marked up for translation" and "readable in your language" are
different claims, and only one of them is what a Filipino-first reader experiences.

**9.3 — the exemption that keeps a fix honest.** Every learn article reported 14–31 controls under 40px
while all 60 calculator pages reported zero. Real — but **WCAG 2.5.8 exempts a link inline in a sentence**,
and forcing 44px on a word inside a paragraph would wreck the line box. The finding is about nav, breadcrumb
and footer links, which are standalone controls; the prose links were left alone. *For Mobile/Designer:* a
raw count of small targets over-states the defect; separate standalone controls from inline text links before
reporting or fixing.

**9.4 — an unserved page reads as an empty one.** A staged page returned "0 labelled elements" and looked
like a total failure; it was a **404** — the dev server does not serve `seo_assets/` at all. *For QA/DevOps:*
read the status code before believing anything about a page's content. (Kin: a search for a call reported it
*before* its own loader because it matched **the comment explaining the fix**.)

**9.5 — right per call, ruinous per wave.** The trajectory writer re-ran the scoreboard generator and the
full registry validator on every invocation: correct for a hand edit, and **30 seconds per row** measured —
a 176-row wave regenerating the roadmap 176 times, about four hours of overhead for one night's rows. A batch
mode that applies many rows in one pass, refusing the whole batch if any entry breaks a rule, replaced it.
*For Performance/Architect:* when a tool moves from interactive to batch use, its per-call fixed cost becomes
the dominant cost — measure it before assuming the data volume is the bottleneck.

## Addendum — 2026-09-08, the contract wave (4 lessons, 8 skill targets)

| # | Lesson | QA | Frontend | Security | AI Eng | DevOps | Architect | Designer | Community |
|---|---|---|---|---|---|---|---|---|---|
| 10.1 | A failover that only triggers on an error cannot trigger on a hang | X | | X | X | X | X | | |
| 10.2 | A shared response helper IS the contract — read it, not the caller's file | X | | | X | | X | | |
| 10.3 | The sign-in door is the worst place to show a code | X | X | X | | | | X | X |
| 10.4 | A cap in the seeder is a cap on the wave, and the prover never knew | X | | | | | X | | |

**10.1 — the failover that could never run.** `_shared/embedding-chain.ts` tries Voyage, then Jina, then
Gemini, then Cloudflare, then a local model, each inside a try/catch that moves on when a call throws. The
design is right. **Not one of its six fetches passed a signal**, and it is imported by eight functions. A
provider that returns an error fails over exactly as intended; a provider that simply *stops answering* does
not — the request waits, and the person waits with it, with no message and no end. *For AI Engineering/
Architect:* every outbound provider call needs a bound, and a retry-or-failover chain without one is
decoration. *For Security/DevOps:* an unbounded upstream is also a way to hold a worker open indefinitely.
Ten calls bounded, using values the platform already uses (15s embed, 30s rerank, 90s gateway — above the 60s
the chain allows itself, so only a genuinely stuck downstream is cut off).

**10.2 — read the helper, not the file.** The contract lens derived each function's response shape from
`JSON.stringify({ key:` in that function's own source, so it took a **push-notification payload** and a
**prompt** for declared responses and accused three functions of a shape they never claimed. **59 of the 62
answer through `_shared/envelope.ts`** — for nearly every function the lens was reading the wrong file. *For
QA:* when a project has a response helper, the helper is the contract; an assertion about shape has to follow
the call, not stop at the file boundary.

**10.3 — a code where a sentence belongs.** `login` answered an empty form with `missing_credentials` and
`supervisor-reset-password` with `missing_hive_or_target`. Both files already knew better — `login` answers a
bad password with `{ error: "invalid_credentials", message: "Wrong username or password." }`. Ten error paths
across the two doors now carry a sentence, and **zero bare-code responses remain across all 62 functions**.
*For Designer/Community:* the sign-in door is where everyone arrives, often already worried about being
locked out, and it is the one screen a person cannot navigate away from to find help. *For QA:* the probe
found one; the sweep found nine more — **fix the class, not the instance the walk happened to hit.**

**10.4 — the seeder's cap versus the prover's roster.** `_shared_components()` ends with `[:14]` while the
prover carries a declared contract for **19** pieces and walks every one — so the wave produced 20 verdicts
about `nav-hub.js` (loaded by 31 pages), `device-fingerprint.js` (33) and three others, with no row to be
written into. *For QA/DevOps:* when a wave reports "verdicts matched no seeded row", that is a roster
disagreement, not noise — compare the two lists. The extension became its own wave code because **the
validator's ids are positional and grouped by wave**: twenty rows inserted into the middle would have
renumbered every row after them and orphaned every basis citing one.

## Addendum — 2026-09-08, the outage stretch (5 lessons, 8 skill targets)

| # | Lesson | QA | Frontend | Security | Mobile | DevOps | Architect | Designer | Data Eng |
|---|---|---|---|---|---|---|---|---|---|
| 11.1 | A question is blocked only if the EVIDENCE it needs is blocked | X | | | | X | X | | X |
| 11.2 | A guard against false readings can produce them | X | X | | | X | | | |
| 11.3 | A lens asking "does it speak to a person" must not read the code first | X | X | | | | | X | |
| 11.4 | An element that appears on a trigger is not a missing element | X | X | | X | | | | |
| 11.5 | A security fix recurs by COPY — sweep for the defect, not the fix | X | | X | | X | | | |

**11.1 — blocked work and blocked evidence are different things.** With the database down for an hour I had
written off the whole remaining queue. Fifty rows were still answerable, because their evidence was in
FILES: whether a gate exercises a page (the registry), whether figures name their period and clock (the
page's text), whether writes leave an audit trail (the page's scripts), how a pasted link behaves (a fresh
browser context needs no data). *For QA/Architect:* when a dependency goes down, re-ask each open question
"where does the evidence for THIS actually live" — the answer is often not where the work normally happens.

**11.2 — the guard I added to stop false readings started producing them.** After the sign-in-door incident I
made every prover compare its landed URL to the page it asked for. The origin carries a `/workhive` prefix,
so a walk that arrived perfectly at `/workhive/achievements.html` was measured against `achievements.html`,
failed a `startsWith`, and was reported as a bounce — 57 correct readings discarded. *The question is "is
this the page I asked for", and the answer lives at the END of the path.* Kin, same hour: a page list written
by Python and read by Node carried `\r` on every line, so 28 of 29 URLs could never match and the one that
"passed" was simply the last line in the file. **A comparison is an instrument too, and both of these
produced confident, precise, wrong numbers.**

**11.3 — the lens punished the fix.** `login` was corrected to answer `{"error":"missing_credentials",
"message":"Enter your username and password to sign in."}` — a code AND a sentence, which is what a good
answer looks like. The lens checked `error` before `message` and reported "a code, not a sentence". *For
QA/Designer:* when a check asks whether output is human-readable, it must prefer the human-readable field;
searching keys in declaration order rewards whichever the developer happened to put first.

**11.4 — a trigger-only element is not a missing one.** `#wh-idle-overlay` is built inside the function that
runs when a session goes idle, so a freshly loaded page correctly has none — and the contract demanded it
unconditionally, producing two findings against a piece behaving exactly as written. The clue was in the
verdict beside it: *"0/3 host(s) carry its element"* next to *"3/3 define whClearIdentity()"*. *For
Frontend/Mobile:* a component contract needs to say WHEN an element exists, not just that it does.

**11.5 — the security fix that recurs by copy.** `Grafana login: admin · password in infra/mcp/.env.mcp` was
removed from one page on 2026-08-25; three siblings carried the identical paragraph three weeks later, and
were worse, because none of them is auth-gated at all. *For Security/DevOps:* grepping for the FIX finds the
page that has it. Only a sweep for the DEFECT across every page finds the ones that do not — and the sweep
has to be a standing gate, because the next paste is a week away.

## Addendum — 2026-09-08, the journey stretch (5 lessons, 9 skill targets)

| # | Lesson | QA | Frontend | Security | Mobile | DevOps | Architect | Designer | Community | Data Eng |
|---|---|---|---|---|---|---|---|---|---|---|
| 12.1 | A walk with no identity grades the sign-in door, silently | X | | X | | X | X | | | |
| 12.2 | A missing link can be the SPEC's route being wrong | X | X | | | | X | X | | |
| 12.3 | Derive the map, never type it — and read the comment before ranking | X | | | | X | X | | | X |
| 12.4 | A test that cannot tell shared content from private state calls a team a leak | X | | X | | | | | X | |
| 12.5 | A tool that serialises work must first serialise itself | | | | | X | X | | | |

**12.1 — the door.** Three provers walked auth-gated pages without signing in. **A sign-in door answers 200
and renders happily**, so nothing in a reading names its own page: one prover graded the door and 37 rows
were banked on it, another detected it and refused 105 of 202, a third still had four. *For QA/DevOps:* every
walk of an auth-gated surface needs an identity AND a check that it landed where it asked; the same blind
spot had already cost the accessibility ratchet its riskiest pages, which is how it was found again.

**12.2 — the spec, not the product.** A journey hopped `logbook → audit-log` and reported "3 hops have no way
onward at all" in six hives. The pages really do not link onward — and the product is right: `nav-hub.js`
marks the destination `hidden: true` with a comment saying *"surfaced via the 'Audit Log' button on
hive.html."* **The archetype's path skipped the route the platform intends.** 24 of 32 archetypes touch such
a destination, so a false navigation defect was about to land on most of 724 rows. *For QA/Architect:* when a
walk says a route is missing, check whether the product documents a different route before calling it a gap.

**12.3 — derive, and read the sentence.** The parent map was first hand-typed and was wrong the moment it was
written (it missed one destination, so a hop was still called a gap). Deriving it needed three fixes, each a
lesson in another coat: re-reading every page for every other was slower than the walk it prepared for; the
landing page links to everything so it won every tie and named nothing useful; and a link-graph guess named
one page where the hub's own comment named another. **Reading the sentence beats ranking the candidates.**

**12.4 — the leak that was a working team.** A shared-device handover test checked whether person A's NAME
survived to person B and reported all sixteen pieces as leaking. A and B are in the same hive: B is *supposed*
to see A's name against A's logbook entries. Rebuilt around a **sentinel only A could have typed**, plus a
refusal to conclude anything if the sentinel never landed. *For Security/Community:* a privacy test needs a
token that is unambiguously one person's, or it will mistake collaboration for disclosure.

**12.5 — self-serialisation.** A driver written to stop concurrent waves had no lock of its own, so two
copies ran and re-created the contention it existed to prevent; the same trap then appeared with two jobs
waiting on one signal. Both drivers now refuse to start beside a live sibling. *For DevOps:* a lock for one
resource is not a lock on the tool that takes it.

