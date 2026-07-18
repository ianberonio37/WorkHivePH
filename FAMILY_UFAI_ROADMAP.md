# FAMILY UFAI ROADMAP — the whole platform against the A–S rubric

**Status:** v1.0 (2026-07-15) · **Owner:** Ian + Claude · **Type:** the cross-page spine.
**Ruler:** `substrate/reference/ufai-ux-rubric.md` (18 classes A–S, ~49 dims).
**Lens:** `survey_ufai_rubric.js` v1.2 (`survey()` + `fingerprint()`).
**Sibling spines:** `HIVE_UFAI_ROADMAP.md` · `HOME_DASHBOARD_UFAI_ARC.md` · `ANALYTICS_UFAI_ROADMAP.md`
(those are PAGE-depth; **this is the FAMILY breadth spine**).

> **Why this exists (Ian, 2026-07-15):** *"what I want is a general lens that can be mirror and
> applicable to all of my platform pages so that my pages would look like not different
> personalities"* → then *"where we at in our Rubric UFAI UIUX for our family pages?"* → then
> **"make sure you fold it as a roadmap, so that we wont be lost."**
> Every prior UFAI arc measured ONE page. This is the first doc that measures the FAMILY.

---

## 0. The headline — and the trap it walks us out of

| Metric | Measured (2026-07-15, live, 32 pages) |
|---|---|
| **S1 family resemblance** | **32/32 = 100%** ✅ (locked by `validate_design_tokens.py` L4) |
| **Full A–S rubric, family mean** | **77% → 96%** (2026-07-16 · see §16 live scoreboard: 31 pages ≥90, 32 ≥85, 0 page errors) |
| **Pages at 100% overall** | **3 / 32** (`hive` · `logbook` · `promo-poster`; the rest 87–99) |
| **Dims at 100% family-wide** | **17 / ~44 scored** (B1 B2 C4 D1 D3 E1 E2 G1 J1 L1 L2 M1 O1 O2 Q1 R4 **S1🔒**) |
| **Top OPEN dims (mean%)** | **N1 73%** (i18n — the outlier) · A2 88 · B3 89 · R3 91 · A1 92 · R1/R2/G3/I2 94 |

**★THE TRAP, NAMED:** I reported "32/32 at 100%" and it was TRUE — of **S1 only, one dim of ~49**.
The family is at **77%**. This is exactly the doctrine's *"one metric at 100% ≠ the roadmap is
done"* — a green headline masking an open axis. **This roadmap exists so that can't happen again:
the scoreboard below carries EVERY page, and "done" means every row, not the row I'm looking at.**

**★Even the exemplars are not 100% — and that is not a regression.** `hive` reads **86%**, not
because it drifted, but because **the ruler grew underneath it**: B3 (readability), E4
(digest-don't-dump) and class S did not exist when hive was driven. A page is only ever "100%
against the rubric as it stood." When the rubric grows, every page re-opens by definition.

---

## ★★ THE METHOD LAW — CENTRALIZED, NEVER PER-PAGE (governs every section below)

**The entire reason this roadmap exists (Ian, 2026-07-15 → reaffirmed hard 2026-07-16):** *"we are
going to have a centralized design style WITH a component library so that we won't hand-edit each
page."* §10 proves the causal mechanic: **a dimension that fails on N pages is almost never N page
bugs — it is ONE unadopted token or component.** So the fix is ONE edit to the shared layer + a
rollout, and **hand-editing 32 pages is the SYMPTOM this roadmap exists to eliminate, never the cure.**

**THE LEVER LADDER — attack in this order, stop at the first layer that can own the fix:**

| # | Layer | One edit reaches… | Owns |
|---|---|---|---|
| **1** | **TOKEN** — `tokens.css` | every CSS-rendered page | brand colour, contrast text tints (`--wh-steel-bright` / `--wh-red-text` / `--wh-violet-text` / `--wh-blue-light`), spacing scale, radii, type. A rebrand is ONE edit here. |
| **2** | **SHARED COMPONENT** — a `components.css` class OR a `utils.js` renderer (`whOhBadge`, `whProgressStrip`, `renderSourceChip`, `whListSkeleton`, `.wh-disclose`, `whFmt*`) | every page that CALLS it | badges, chips, cards, buttons, progress strips, source chips, skeletons, disclosures, formatters. Work is usually **ADOPTION**, not building — the library is already built (§10). |
| **3** | **SHARED SCRIPT injected platform-wide** — via `nav-hub.js` (the i18n floor, `learn-link.js`, freshness chips) | all ~29 pages, from ONE file | cross-page chrome + behaviours. One file, never 29 edits. |
| **4** | **PER-PAGE — LAST RESORT ONLY** | one page | ONLY genuinely page-UNIQUE content no shared layer can own: a page's own headline copy, its unique i18n dictionary VALUES. |

**THE TEST before any page edit:** *"Is this value or pattern shared across pages?"* If yes →
**promote it to layer 1–3 and adopt; do NOT hand-patch this page.** A hardcoded `rgba(255,255,255,0.5)`
inline on 16 pages is not 16 bugs — it is one missing utility. If you catch yourself editing the same
*pattern* on page 2, STOP and lift it up a layer.

**★THIS SESSION'S VIOLATION (own it, don't repeat):** the 2026-07-16 drive hand-edited ~16 pages'
text colours, 12 pages' tap-target min-heights, and 17 pages' copy. Some landed correctly in the
shared layer (`tokens.css` gained the contrast tints; `utils.js` gained `whOhBadge` + `whProgressStrip`;
`skill-content.js`/`utils.js` colour maps were centralised) — **but far too much was per-page grind,
the exact symptom §10 names.** From here, every open dim converts to a token / component / script
lever + a rollout + an adoption gate — the per-page path is closed unless the content is provably unique.

**THE OPEN DIMS, MAPPED TO THEIR LEVER (not a page list):**

| Open dim | mean% | Centralized lever (the ONLY sanctioned fix) |
|---|---|---|
| **N1 i18n** | 73 | **Layer 3** shared-chrome i18n (`nav-hub`/`companion-launcher` translated once = 29 pages) + **Layer 2** `whI18nApply` + `whFmt*` adoption. Layer 4 (per-page) ONLY for each page's unique dictionary VALUES. |
| **A2 scannability** | 88 | **Layer 2** a shared section-header/`.wh-section-label` component so headings are structural everywhere. |
| **B3 readability** | 89 | AI copy → the **system PROMPT** (one edit, per `ai-engineer` skill). Static copy → Layer 4 (genuinely unique sentences). |
| **R3 treatment uniformity** | 91 | **Layer 2** adopt `.simple-card`/`.action-card` + the shared control (tab-bar) vocabulary. |
| **A1 5-second test** | 92 | **Layer 2** a shared page-header component (one `<h1>` + one focal tier). |
| **R1 spacing** | 94 | **Layer 1** spacing tokens + a shared spacing utility; snap off-scale gaps at the token, never per page. |
| **R2 overflow** | 94 | **Layer 2** a shared `overflow-x:auto` scroll-wrapper class for wide tables. |
| **C1 hierarchy / I2 perf / K2 reach / G3** | 94–95 | **Layer 2** component adoption (`renderKpiTile`, skeletons, glanceable-KPI class). |
| **C2 contrast / F1 tap** | 99 | residue is inline strays → **promote to Layer 1 token / Layer 2 `.wh-text-muted` + `.wh-tap` utilities**, never more per-page nudges. |

**The locking gate stays F7** (`validate_family_rubric_ratchet.py`) for the score, PLUS the §10.4
**adoption gate** (a component-registry check) so a rolled-out component can't silently rot back to 0.

---

## 1. The scoreboard — all 32 family pages, MEASURED (never asserted)

Method: live Playwright, `window.__RUBRIC.survey()` on the **worked state**, `OVERALL_measured_pct`
= passing/total across MEASURED dims only (JUDGED + N/A excluded — never invented).

| Page | Overall | Open dims |
|---|---|---|
| **analytics** | **98%** | B3 67 · R3 67 |
| pm-scheduler | 91% | A2 50 · A3 75 · B3 67 · C2 83 · H1 0 · N1 25 · R3 67 |
| asset-hub | 89% | A2 50 · A3 75 · B3 67 · C2 99 · G1 0 · H1 0 · N1 25 |
| skillmatrix | 89% | A1 75 · A2 50 · A3 75 · C2 98 · G1 0 · H1 0 · N1 25 · R3 67 |
| **hive** (exemplar) | 86% | A1 75 · A2 50 · A3 75 · C1 33 · G1 0 · H1 0 · J1 0 · R3 67 |
| project-manager | 86% | A2 50 · A3 75 · B3 67 · F1 76 · H1 0 · K2 0 · N1 25 |
| **index** (exemplar) | 85% | A1 75 · A2 25 · A3 75 · C3 50 · E3 50 · F1 88 · G1 0 · H1 0 · K2 50 · R3 67 |
| marketplace | 84% | A1 75 · A2 50 · A3 75 · C2 94 · G1 0 · H1 0 · H4 0 · N1 25 · R1 40 · R3 33 |
| shift-brain | 84% | A2 50 · A3 75 · B3 0 · C2 88 · E4 67 · F1 81 · H1 0 · J1 0 · K2 50 · N1 25 |
| inventory | 82% | A2 50 · A3 75 · C2 70 · C4 0 · G1 0 · H1 0 · N1 0 · R1 25 · R2 0 |
| dayplanner | 80% | A2 50 · A3 75 · B3 67 · C2 41 · G1 0 · H1 0 · H4 0 · K2 50 · N1 25 |
| report-sender | 80% | A1 75 · A2 50 · A3 75 · B3 33 · C2 88 · E2 50 · H1 0 · K2 50 · N1 25 · O2 0 · R3 33 |
| alert-hub | 78% | A1 75 · A2 50 · A3 75 · B3 33 · C1 67 · G1 0 · H1 0 · J1 0 · N1 25 · R1 0 · R3 67 |
| logbook | 78% | A1 75 · A3 75 · C2 77 · E2 0 · E3 0 · G1 0 · H1 0 · J1 0 · K2 50 · N1 25 |
| community | 78% | A1 75 · A2 25 · A3 75 · C3 50 · F1 84 · G1 0 · H1 0 · J1 0 · K2 0 · N1 25 · R3 67 |
| assistant | 78% | A1 25 · A2 25 · A3 75 · C2 71 · C3 50 · E3 0 · G1 0 · H1 0 · K2 50 · N1 25 |
| engineering-design | 78% | A2 50 · A3 75 · B3 67 · C2 96 · E3 50 · F1 92 · G1 0 · H1 0 · K2 0 · N1 25 |
| achievements | 76% | A1 75 · A2 50 · A3 75 · B1 67 · B2 0 · B3 67 · C1 67 · C2 60 · G1 0 · H1 0 · K1 52 · K2 50 · N1 25 · R3 67 |
| voice-journal | 76% | A1 75 · A2 75 · A3 75 · B3 33 · C2 76 · C3 50 · E3 0 · G1 0 · H1 0 · K2 50 · N1 25 · R3 33 |
| integrations | 75% | A1 75 · A3 75 · B3 33 · E2 0 · E3 0 · F1 94 · G1 0 · H1 0 · K2 0 · N1 25 · R1 33 · R3 67 |
| plant-connections | 75% | A1 50 · A2 50 · A3 75 · B3 33 · C1 67 · G1 0 · H1 0 · K2 50 · N1 25 · O2 0 · R3 67 |
| ai-quality | 73% | A1 75 · A2 50 · A3 75 · C2 76 · G1 0 · H1 0 · I2 0 · K2 50 · N1 25 · O2 0 · R1 0 |
| project-report | 72% | A1 75 · A2 75 · A3 75 · B3 33 · C3 50 · E3 0 · F1 0 · H1 0 · K2 0 · N1 25 · O2 0 |
| marketplace-seller | 72% | A1 75 · A2 75 · A3 75 · C2 92 · C3 50 · E2 0 · E3 0 · G1 0 · H1 0 · J1 0 · K2 50 · N1 25 · O2 0 · R1 33 · R3 67 |
| marketplace-admin | 71% | A1 75 · A2 25 · A3 75 · C2 82 · C3 50 · C4 0 · E3 0 · G1 0 · H1 0 · J1 0 · N1 25 · O2 0 · R1 33 · R3 67 |
| agentic-rag-observability | 71% | A1 75 · A3 75 · B3 67 · C4 0 · E2 67 · E3 0 · G1 0 · H1 0 · I2 0 · J1 0 · N1 25 · O2 0 · R1 50 |
| audit-log | 70% | A1 75 · A2 25 · A3 75 · B3 67 · C3 50 · G1 0 · H1 0 · J1 0 · K2 50 · N1 0 · R1 0 · R2 0 · R3 67 |
| marketplace-seller-profile | 69% | A1 50 · A2 50 · A3 75 · C3 50 · E2 0 · E3 0 · G1 0 · H1 0 · I2 0 · K2 50 · N1 25 · O2 0 |
| public-feed | 69% | A1 75 · A2 25 · A3 75 · C3 50 · E3 0 · E4 67 · G1 0 · H1 0 · I2 0 · K2 50 · N1 25 · O2 0 · R1 50 |
| status | 68% | A1 75 · A3 75 · C2 96 · E3 0 · G2 0 · H1 0 · I2 0 · K2 50 · N1 25 · O2 0 · Q1 0 · R1 0 |
| ph-intelligence | 66% | A1 75 · A2 25 · A3 75 · B1 67 · B2 0 · B3 0 · C2 82 · C3 50 · E3 0 · G1 0 · H1 0 · K2 50 · N1 25 · O2 0 |
| **promo-poster** | **52%** | A1 50 · A2 25 · A3 75 · B3 0 · C1 67 · C2 96 · C3 50 · E3 0 · G1 0 · H1 0 · H4 0 · I2 0 · K2 50 · N1 0 · O2 0 · Q1 0 · R2 0 |

---


## 1b. THE PER-DIMENSION SCOREBOARD — every class, every dim, family-wide % (v1.1, 2026-07-15)

> Ian: *"I want a UFAI UI UX for my family pages, so that we have our own CENTRALIZED design style
> with component library... a roadmap with each class and dimensions with percentage."*
> % = family pages PASSING that dim (pass = dim at 100 on that page) / 32, from the live sweep.
> JUDGED dims carry no % by the honesty contract. G1 uses the CORRECTED number (§11); N1 shows the
> HONEST split (§9): mechanism vs actual translation.

| Class | Dim | Family % passing | Owning component / lever | Adoption | Phase |
|---|---|---|---|---|---|
| **A · Attention** | A1 5-second test | **25%** (8/32) | answer-first headline pattern (extract from the E4 card work) | to extract | F2 |
| | A2 Scannability | **16%** (5/32) | same cluster as A1 | to extract | F2 |
| | A3 Progressive disclosure | **3%** (1/32) | **`.wh-disclose` + `wireDetailToggle` — EXISTS, finished** | **1/32 (hive)** | F2 |
| **B · Copy** | B1 Microcopy/concision | 94% | plain-language gate (exists) | — | F6 |
| | B2 Plain voice & tone | 94% | same | — | F6 |
| | B3 Readability (<=20w, grade<=8) | **44%** (14/32) | copy sweep + AI-prompt rules (proven on analytics) | recipe proven | F2 |
| **C · Visual** | C1 Visual hierarchy | 84% | `renderKpiTile` + type-scale tokens | 2/32 | F6 |
| | C2 Colour & contrast | **41%** (13/32) | token/opacity sweep (mostly near-misses; dayplanner 41 + achievements 60 real) | style guide | F4 |
| | C3 Whitespace/gestalt | 63% | spacing tokens (exist) | — | F4 |
| | C4 Tabular KPIs | 91% | `font-variant-numeric` token | — | F6 |
| **D · Affordance** | D1 Signifiers · D3 One vocabulary | 100% | tokens | — | ✅ |
| **E · Evidence** | E1 Data-viz/KPI | 100% | chart rules (rubric E1) | — | ✅ |
| | E2 Empty/loading/error | 81% | **`whListSkeleton` + `whListError` — EXIST, self-injecting** | partial | F3 |
| | E3 Trust/transparency | **53%** (17/32) | **`renderSourceChip` — the ADOPTION PROOF: 20/32 adopted → healthiest of the failing dims** | 20/32 | F3 |
| | E4 Digest, don't dump | 94% | Miller-cap + verdict-once pattern (built this session) | analytics | F6 |
| **F · Reach** | F1 Touch >=44px | 78% | 44px floor tokens (`--wh-control-h`) | — | F6 |
| | F2 WCAG (axe) · F3 Peak-end | JUDGED | ufai_battery.js owns F2 | — | — |
| **G · Nielsen** | **G1 System status** | **13% (4/32) — CORRECTED §11** | **`whFreshnessChip` — BUILT + live-verified this session** | **0/32** | **F3** |
| | G2 Match real world | 97% | — | — | F6 |
| | G3 Aesthetic-minimalist | 100% | — | — | ✅ |
| **H · Motivation** | **H1 Goal-gradient** | **3%** (1/32) | per-page progress model (hive stairs = exemplar) — NOT componentizable | design | F5 |
| | H2 Zeigarnik · H3 Serial position | JUDGED | — | — | — |
| | H4 Selective attention | 91% | — | — | F6 |
| **I · Performance** | I1 Core Web Vitals | JUDGED (battery owns) | — | — | — |
| | I2 Perceived performance | 81% | **`whListSkeleton`** (the skeleton satisfies I2, the TRANSIENT dim — not G1; §11's mapping rule) | partial | F3 |
| **J · Control** | J1 Prevent slips | 72% | `whConfirm` / `whPrompt` | 15/32 | F3 |
| | J2 Forgiveness/undo | 100% | — | — | ✅ |
| **K · Field-first** | K1 Safety signalling (no colour-alone) | 97% | badge+icon pattern | — | F6 |
| | K2 Field legibility & reach | **31%** (10/32) | type-size floor at arm's length (style guide) | tokens | F4 |
| **L · Honesty** | L1 No deceptive patterns · L2 Info scent | 100% | — | — | ✅ |
| **M · Forms** | M1 Labels · M2 Validation | pass / N/A | form pattern (hive v4) | — | ✅ |
| **N · i18n** | **N1** | **mechanism: ~100% (floor, §9) · REAL translation: ~3/32** | locale floor ✅ + `nav-hub`/`companion` ✅ + `whFmt*` (0/32) + per-page dicts + `i18nCoverage()` honest measure | floor DONE | **F1** |
| **O · Onboarding** | O1 Value-first | 100% | — | — | ✅ |
| | O2 Pull > push help | 63% | `.wh-prov-btn` / details help affordance | partial | F6 |
| **Q · Motion** | Q1 prefers-reduced-motion | 94% | one media block (components.css) | — | F6 |
| **R · Rhythm** | R1 8-pt spacing | 66% | spacing tokens | — | F4 |
| | R2 Alignment/grid | 91% | — | — | F6 |
| | R3 Treatment uniformity | **50%** (16/32) | silhouette tokens (pill=select · rect=press) — press+select on phase-tabs = IAN'S CALL | tokens | F4 |
| | R4 Regions · R5 Vertical flow | 100% / JUDGED | — | — | ✅ |
| **S · Family** | **S1 Token conformance** | **100% (32/32) — LOCKED (L4 ratchet)** | `tokens.css` + `EXCLUDE` scope | **DONE** | ✅ F0 |

**Reading order of the fires (impact × cheapness):**
1. **G1 13%** — 28 pages, component ALREADY BUILT → pure adoption. Cheapest big win.
2. **A3 3%** — 31 pages, component EXISTS (`.wh-disclose`), hive is the reference impl.
3. **H1 3%** — 31 pages but per-page DESIGN work (not componentizable) → phased last (F5).
4. **N1** — floor done; real translation needs per-page dicts + the honest `i18nCoverage()` number.
5. **A1 25% / A2 16%** — the answer-first cluster; extract the pattern from the E4 card work.
6. **K2 31% / C2 41% / R3 50%** — style-guide sweeps (tokens/opacity), low risk.

---

## 2. §SYNTHESIS — this is NOT 32 page problems. It is ~6 platform patterns.

*(Synthesis is the deliverable, not the register — the map is the instrument.)*

The same dims fail on nearly every page. **One fix per pattern lifts the whole family**, which is
why this is a roadmap and not 32 tickets.

| Pattern | Fails on | The job-to-be-done | Verdict |
|---|---|---|---|
| **P1 · N1 i18n** | **29/32** | EN/FIL parity | **FUSE — one proven recipe, 29 pages.** `WH_LANG` + `_t()` + `wh-locale-change` re-render, proven on analytics + hive + home. Mechanical, highest-leverage. |
| **P2 · A3 progressive disclosure** | **31/32** | don't show everything at once | **FUSE with P3** — same root: the page dumps instead of leading. Sibling of the E4 work already done on analytics' cards. |
| **P3 · A1+A2 answer-first** | 24 + 27 | 5-second test · scannability | **FUSE with P2.** A1/A2/A3 are one cluster: *lead with the answer, disclose the rest.* |
| **P4 · H1 goal gradient** | **31/32** | "how far along am I" | **KEEP DISTINCT** — needs a per-page progress model, not a shared component. Hive's stairs are the exemplar. |
| **P5 · G1 system status** | 25/32 | freshness / sync / "as of" | **FUSE — one shared affordance.** The same "last refreshed · auto-refresh" chip analytics already ships. |
| **P6 · C2 contrast** | 19/32 | WCAG AA | **SWEEP, low-risk.** Mostly near-misses (70–99%), a token/opacity nudge. `dayplanner 41%` + `achievements 60%` are the real ones. |

**Not a pattern (page-local):** C4 tabular numerals (inventory/marketplace-admin/agentic-rag),
R1/R2 rhythm (audit-log/inventory/promo-poster), F1 tap targets (project-report 0%, a real find).

---

## 3. Phases — each row carries a MEASURED target and a LOCKING gate

**No phase is "done" on vibes; each lands a % and a ratchet so it cannot seesaw back.**

| # | Phase | Now (2026-07-16 sweep) | Target | Locking gate |
|---|---|---|---|---|
| **F0** | **Family resemblance (class S)** | **100%** ✅ | 100% | `validate_design_tokens.py` **L4** (rogue-radius ratchet, falsifiable) — **DONE + LOCKED** |
| **F1** | **P1 · N1 i18n across 32 pages** | 1/32 green (recipe PROVEN on hive: data-i tags + translate="no" on data + dict keys) | 32/32 | extend the i18n coverage gate; EN↔FIL round-trip + axe-clean in both |
| **F2** | **P2+P3 · answer-first cluster (A1/A2/A3)** | 92/86/98 mean | 100% | **F7 ratchet** (`validate_family_rubric_ratchet.py`) holds every green dim |
| **F3** | **P5 · G1 status affordance** | **31/32** (promo = poster N/A) | 32/32 | shared chip + presence assert |
| **F4** | **P6 · C2 contrast sweep** | **3 open** (mean 99%) | 0 open | contrast floor in the a11y gate (measure, never trust axe `violations` alone) |
| **F5** | **P4 · H1 goal gradient** | **5/6 worker-daily live** (whProgressStrip; logbook team-state pending re-verify) | per-page judged | per-page; whProgressStrip is the shared component |
| **F6** | page-local residue (C4 ✅0 / R1 7 / R2 2 / F1 3) | small singles | 0 | existing per-page gates |
| **F7** | **ADOPTION RATCHET — the whole-board lock** | **LIVE: mean 96 · 31≥90 · 32/32≥85 baselined** | forward-only | `tools/validate_family_rubric_ratchet.py` (mean + per-page −2 tolerance + green-dim holds; refuses partial boards) |

---

## 4. The ruler's OWN corrections — instrument bugs found by probing before fixing

**Every one of these would have shipped a REGRESSION or a FALSE 100.** Banked because the lens is
now the platform's ruler: if the ruler lies, every number downstream lies.

| Bug | What it would have done |
|---|---|
| **`parseFloat('50%') === 50`** | read voice-journal's `border-radius:50%` on a **116×116 circular mic button** as "50px rogue" → **would have squared off a signature control**. A `%` radius is a shape INTENT → `round`. |
| **loaded vs fallback typeface** | flagged project-report's **IBM Plex Sans** (deliberately `@font-face`-loaded for its printable `#ar-print-wrapper`, 11pt on paper) identically to alert-hub's **Arial** (never loaded, a UA leak) → **would have destroyed an intentional document typeface**. `document.fonts` IS the intent record. |
| **offline page + webfont** | `sw.js` serves fonts **network-first with a 503 fallback**, so Poppins is unavailable on `offline-fallback` **by definition**. Setting `var(--wh-font)` would **PASS the rubric while rendering the identical fallback** = a textbook false-100. Its system stack is CORRECT. |
| **`\b` → BACKSPACE (0x08)** | a non-raw Python heredoc silently killed the E4 regex → reported **`rawIdDumps=0`** on a card visibly listing **26 asset codes**. **Every detector now needs a positive + negative control before a zero is believed.** |
| **closed `<details>`** | hides via the UA slot, so a collapsed child still reports `display:inline` + a real 315×45 rect → the lens counted disclosed content as an on-screen dump. |
| **FK below ~12 words** | flagged "Recommended: Daily (currently Weekly)" (8 words, unambiguous) at grade 8.9 → applying a metric OUTSIDE its validity range invents work. |

---

## 5. Scope — what IS the family (Ian's decisions, 2026-07-15)

| Class | Pages | Why |
|---|---|---|
| **IN — the family (32)** | the user-facing platform | what users actually see |
| **OUT — internal tooling** | `architecture`, `validator-catalog`, `llm-observability`, `symbol-gallery` (+ pre-existing `platform-health`, `founder-console`) | dev/ops surfaces, ship no webfont. In `validate_design_tokens.py` `EXCLUDE`. Excluding them tightened L3 463→461 + L4 268→258 **honestly**. |
| **OUT — distinct artifacts (CITED)** | `resume.html` (a CV), `promo-poster.html` (a poster) | standalone deliverables, same class as `project-report`'s print doc. **Cited so nobody "fixes" them into the family later.** |
| **EXCEPTION — cited** | `offline-fallback` typeface · `project-report` IBM Plex | deliberate opt-outs, proven not assumed |

> `promo-poster` appears in the §1 scoreboard at 52% for visibility, but is **OUT of the family
> metric** per the decision above. A cited 32/33 beats a manufactured 33/33.

---

## 6. NEXT queue (load-bearing on resume — this is the trajectory)

1. **F1 · N1 i18n** — 29 pages, the proven recipe. Highest leverage, mechanical, gate-able.
2. **F2 · A1/A2/A3 answer-first cluster** — same root as the E4 card work already landed.
3. **R3 residual (analytics 67%)** — `8px worn by press+select`: the phase-tabs became `select` once
   given `aria-pressed` and sit at 8px while other selects are pills. **A view-switcher looking like
   an action button is a DESIGN QUESTION for Ian** (pill it? own vocabulary? full
   `role=tablist`+arrow-keys?). Not a defect.
4. **B3 residual** — grade>8 sits on FORMULA/decoder lines (`Prediction = …`, `Weights: 30% …`).
   Exempt formula-shaped lines like the standards exemption?
5. **IAN-GATED:** python-api **image rebuild** (`prescriptive.py` + `diagnostic.py` are live via
   `docker cp` ONLY) + **commit the tree**. STAY LOCAL until Ian initiates.

---

## 7. Method (unchanged from the prior UFAI arcs)

ground in the substrate → **measure the WORKED state live** (never the empty shell) → synthesise into
patterns → drive with a % per row → **verify each fix live** → **ratchet-lock** (forward-only) →
teach the skills → persist (memory + this doc). **Measured-%, not vibes. No false 100.**
A dim with no honest denominator reports **JUDGED**; a dim whose subject is absent reports **N/A**
with the ROOT CAUSE — **never a blaming 0**.

---

## 8. §NIGHT-CRAWLER SWEEP (2026-07-15) — the honest yield: **we already had it**

Ian: *"can also fan out a night crawler how we can solve this problem internal and external sources,
perhaps you can also get some ideas, who knows."* Run, and reported honestly:

| Pattern | Bag status | Verdict |
|---|---|---|
| P2 A3 disclosure | `ux-progressive-disclosure-defer-complexity` | **already owned** |
| P3 A1/A2 answer-first | `f-pattern` · `information-scent` · `scanning-how-users-read` · `visual-hierarchy` · `dashboard-design-aggregate-summarise` | **already owned (5 chunks)** |
| P4 H1 goal gradient | `ux-goal-gradient-motivation-progress` | **already owned** |
| P5 G1 status | `visibility-of-system-status` · `indicators-validations-notifications` · `skeleton-screens` | **already owned (3)** |
| P6 C2 contrast | `ux-wcag-contrast-ratio-4-5` | **already owned** |
| **P1 N1 i18n** | no external chunk… **but the RUBRIC already encodes the rule** | **already owned — see below** |

**★THE FINDING: the substrate is MATURE. 61 chunks already cover 5 of 6 patterns, and the 6th was
covered in the RULER itself.** N1 already reads: *"translated strings run ~25-35% longer
(Tagalog/Cebuano); layout must not break; never concatenate strings; **locale-format
numbers/dates/₱**; offer a language switch. **(Source W3C qa-i18n was bot-blocked → applied from
domain knowledge.)**"* — **a past session already tried that crawl, got bot-blocked, and RECORDED it.**
I re-ran the same crawl and rediscovered it. **The retrieve-first rule exists for exactly this;
I should have read N1 before crawling.**

**The two crawls' actual yield:**
- W3C `article-text-size` → **JS-rendered stub (509 chars)** → distilled to *"No specific rules
  found"* → **DELETED.** A null chunk poisons future retrieval (a later query would hit it and
  conclude we own nothing). **Verify a URL returns real static text before spending a crawl** — 3 of
  5 candidate NN/g URLs were **404**, and a 404 distils into a "page-not-found" chunk.
- MDN `Glossary/Localization` → kept, **modest**: localization ⊃ translation (units, text direction,
  capitalisation, idiom, register, number/date/currency format, colour psychology, local law).
  Confirms N1's `locale-format numbers/dates/₱` rather than extending it.

**★THE OPERATIONAL CONCLUSION: the lever is APPLICATION, not more knowledge.** We are not short of
cited rules — we are short of pages that obey the ones we have. **F1 (N1 across 29 pages) needs zero
new research**: the recipe is battle-tested internally (`WH_LANG` + `_t(en,fil)` + `_tv()` phrase-map
+ `setLang()` + static `data-i` + FIL dict + **sync-on-load** + safe `_t` fallback in shared
renderers + `documentElement.lang` + **DATA stays English**), with its gotchas paid for in blood on
hive/home (`data-i` on an `<a>` holding an SVG nukes the icon; a per-state `h1` trips multiple-h1;
inline `onclick` trips the CSP ratchet; every new empty `catch` needs the allow-marker + a sibling
sweep). **Go execute it.**

---

## 9. F1 STARTED — the design-system lever, PROVEN (2026-07-15)

**What the night-crawl actually taught (§8's real payload):** NN/g defines a design system as
**"a style guide PLUS a component library ... reducing REDUNDANCY and creating a SHARED LANGUAGE
across pages"**; Brad Frost's atomic design says organisms are **"standalone, portable, REUSABLE
components."** **We had the style guide (`tokens.css`) and NOT the component library.** That is
measurably WHY the family grinds page-by-page and why the same dims fail on all 32.

**The redundancy, measured:** the i18n ENGINE was pasted inline **4×** (analytics / hive / index /
analytics-report) while the SHARED chrome was **100% English**: `utils.js` reaches **35 pages**,
`nav-hub.js` **31**, `companion-launcher.js` **29** — and none could translate a word.

**The lever pulled (2 file edits, not 29):**
- `utils.js` gained the **i18n LOCALE FLOOR** — `WH_LANG` + `_t(en,fil)` + `<html lang>`, defensive
  (a page with its own engine still wins; both read the same `wh_lang` key). Same lever this file
  already used for the focus ring *"without editing 40+ pages individually."*
- `nav-hub.js` (31 pages) now translates its 4 user-facing strings via the safe-`_t` convention.
- **Live-verified on pages with NO engine of their own** (inventory / logbook / alert-hub):
  `WH_LANG=fil`, `_t=function`, `<html lang>=fil`, nav renders **"Maghanap ng assets, trabaho,
  parts, PM" · "Kamakailan" · "Lahat ng Tools"**, **0 page errors**. **Pick Filipino once on the
  home dashboard and it now follows you across the platform's chrome.**

### ★★THE TRAP I WALKED INTO AND CAUGHT — installing the MECHANISM must never BE the win

Adding the locale floor took logbook/alert-hub/community **N1 25% → 75%** — while those pages still
rendered **0/12, 0/49, 0/24** translated labels. **A page that is 100% English scored 75%.** I
manufactured that number by installing the very mechanism N1 checks for. It is the same false-100
this whole arc keeps catching, and this time **I caused it.**

Worse, the obvious fix (count `data-i`) is ALSO wrong: **analytics reports `0/22` while being fully
bilingual**, because it translates JS-rendered content through **`_t()` at render time**, not
`data-i`. A `data-i` proxy under-counts our BEST page.

**Disposition (honest, not faked):** N1 is renamed **"i18n mechanism + expansion resilience (NOT %
translated)"**, the note now carries `label coverage` as the honest signal, and the limitation is
written into the lens itself. **A truthful coverage number needs a LOCALE-FLIP DIFF** — snapshot the
labels, `setLang('fil')`, re-snapshot, count what changed: mechanism-agnostic and outcome-true. It
is a real instrument change (`setLang` re-renders, so element handles go stale), so it is **QUEUED,
not bluffed**.

**★THE RULE THIS ADDS: when a fix moves a metric, ask whether it moved the OUTCOME or just the
thing the metric happens to look at.** A shared engine is genuine user value (the chrome IS Filipino
now, `lang` IS correct) — but it is not translation, and the scoreboard must not say it is.

**NEXT for F1:** (1) build the locale-flip-diff coverage measure; (2) translate the remaining shared
chrome (`companion-launcher.js`, 29 pages) — the same 2-edit lever; (3) only THEN per-page dicts,
where the cost is genuinely per-page.

---

## 10. ★THE COMPONENT LIBRARY ↔ RUBRIC INDEX — the root cause, measured (2026-07-15)

> Ian: *"I want these one for our Rubric UFAI UIUX each class and dimensions, so that it would be
> easier now to handle our family pages. NN/g defines a design system as 'a style guide plus a
> component library… reducing redundancy and creating a shared language across pages.' Brad Frost:
> organisms are 'standalone, portable, reusable components.' **We had the style guide (tokens.css)
> and never built the component library.** That's measurably why the family grinds page-by-page and
> why the same dims fail on all 32 pages."*

**The measurement corrects the thesis in the ONE way that matters — and makes it CHEAPER.**
**We DID build the component library. We never ADOPTED it.**

### 10.1 The index — component → the dim it satisfies → measured adoption

| Component | Type | Satisfies | Adoption | That dim FAILS on |
|---|---|---|---|---|
| **`.wh-disclose`** (+ `wireDetailToggle`) | CSS + behaviour | **A3** progressive disclosure | **1/32** (`hive` only) | **31/32** |
| **`whListSkeleton(el, rows)`** | JS renderer, `aria-busy`+`aria-live`, **self-injecting CSS** | **G1** visibility of system status | **0/32** | **25/32** |
| **`whFmtDate` / `whFmtNum` / `whFmtPeso` / `whFmtDuration`** | JS formatters | **N1** locale-format numbers/dates/₱ | **0 / 0 / 4 / 0** | **29/32** |
| `renderKpiTile` | JS renderer | **C1** KPI type scale | 2/32 | (C1 open on 4) |
| `renderSourceChip` | JS renderer | **E3** provenance | **20/32** | (E3 among our HEALTHIEST) |
| `.simple-card` / `.action-card` / `.tile` | CSS | **R3** container uniformity | 17/32 | (R3 mostly passing) |
| `whConfirm` / `whPrompt` | JS | **J2** user control / confirmation | 15/32 | (J-class mostly fine) |
| `renderRiskStrip` / `renderPmDueStrip` / `renderPartsStrip` / `renderActionBrief` | JS renderers | cross-page canonical reuse | — | — |
| **`utils.js` locale floor** (NEW §9) | JS | **N1** mechanism | **35/32 reach** | — |
| **`nav-hub.js` / `companion-launcher.js`** (NEW §9) | shared chrome, now bilingual | **N1** chrome | **31 / 29** | — |
| **`whI18nApply` + `window.WH_FIL_PAGE`** (NEW 2026-07-16) | JS applier in utils.js | **N1** static-label swap on engine-less pages | rolling out | (N1 open on ~16) |
| **`.wh-text-muted` / `.wh-text-faint`** (NEW 2026-07-16) | tokens.css utility + `--wh-text-muted` | **C2** muted secondary text (AA floor) | 0/28 (just built) | was inline on 19 |
| **`.wh-num`** (NEW 2026-07-16) | tokens.css utility | **C4** tabular figures | 0/28 (just built) | was inline on 16 |
| **`.wh-tap` / `.wh-tap-h`** (NEW 2026-07-16) | tokens.css utility (`--wh-control-h`) | **F1** 44px tap floor | 0/28 (just built) | was inline on 12 |

### 10.2 ★THE CAUSAL LINK IS EXACT — the dims fail precisely where the component is unadopted

- **`.wh-disclose` adopted by 1 page → A3 fails on 31.** The one adopter is `hive` — **the exemplar
  uses the library; nobody else does.**
- **`whListSkeleton` adopted by 0 → G1 fails on 25.**
- **`whFmtDate`/`whFmtNum` adopted by 0 → N1 fails on 29.**
- **Inverted control (the proof runs both ways): `renderSourceChip` at 20/32 adoption → E3 is among
  the healthiest dims on the board.** High adoption ⇒ the dim passes. This is not a coincidence; it
  is the mechanism.

**These are not half-built parts.** `.wh-disclose` ships its summary marker, the rotate affordance,
a `prefers-reduced-motion` variant and a body slot. `whListSkeleton` ships `aria-busy` + `aria-live`
and **self-injects its own CSS** (STREAMLINE E2) — **zero setup: any utils.js page can call it
today.** They are finished, portable organisms with ~0% uptake.

### 10.3 What this REFRAMES in this roadmap

**§3's phases are ADOPTION phases, not BUILD phases.** F2 (A3), F3 (G1) and part of F1 (N1
formatters) were scoped as "design and build a shared affordance". **The affordance already exists.**
The work is *rollout + a gate that keeps it adopted* — dramatically cheaper, and it explains the §2
synthesis mechanically: the same dims fail on all 32 pages **because the same components are
unadopted on all 32 pages.**

**★THE STANDING RULE THIS ADDS:** before building ANY shared affordance for a failing dim, **grep the
adoption of the component that already satisfies it.** We have twice now nearly rebuilt something we
already owned (the i18n engine was pasted inline 4× while `utils.js` sat unused for it). *Retrieve-
first applies to COMPONENTS, not just knowledge.*

**A component with 0% adoption is indistinguishable from a component that does not exist — except it
already cost us the build.** The library is not the deliverable; **adoption is.**

### 10.4 NEXT (supersedes §3's F2/F3 framing)

> **★ABSORBED (2026-07-16) into `FULLSTACK_COMPONENT_LIBRARY_ROADMAP.md` §2 (Layer F)** — the
> master spine that generalizes this section to all 13 full-stack layers. ONE queue, not two:
> this list is now executed as that spine's **F-P3 rollout waves**, measured by
> `tools/component_adoption_census.py` against `design_component_registry.json` (SSOT) and locked
> by `validate_component_adoption.py` (item 4 below = BUILT, registered in `run_platform_checks`,
> forward-only floors + auto-tighten). FAMILY_UFAI keeps the rubric SCORE board; the spine owns
> the ADOPTION board.

1. **Adopt `whListSkeleton` on the 25 G1-failing pages** — one call per async list; CSS self-injects.
   *(→ spine wave ①; measured 12/29 at census time.)*
2. **Adopt `.wh-disclose` + `wireDetailToggle` on the A3-failing pages** — hive is the reference impl.
   *(→ spine wave ②; measured 17/32.)*
3. **Adopt `whFmtDate`/`whFmtNum`** wherever a date/number renders (closes N1's locale-format half).
   *(→ spine wave ③; measured 0/30 and 0/19.)*
4. **Gate adoption** so it ratchets — an unadopted component silently rots back to 0 (a component
   registry check in `run_platform_checks`, forward-only, same shape as L4). ✅ **BUILT 2026-07-16**
   = `validate_component_adoption.py`.

---

## 11. ★RULER CORRECTION — G1 was a FALSE-PASS FACTORY; the real freshness component IS the fix (2026-07-15)

Proving §10 by adopting the "G1 component" surfaced a bug in G1 ITSELF — the exact thing that makes
this a measured roadmap and not a vibe.

**The bug:** G1's selector `[class*="status"]` matched **`.status-badge` / `.status-pill`**, which
carry an **asset's** status ("Overdue", "Closed", "draft") — DATA, not SYSTEM status. **pm-scheduler,
shift-brain and hive all "passed" G1 for rendering the word "Overdue" in a data badge.** Same
substring trap that once matched a COMMENT instead of a `<link>`: **a class NAME is not a role.**

**The correction:** G1 now requires real system-status semantics (`#status-bar`, `[role="status"]`,
a non-data `[aria-live]`), so the number drops to the truth: **G1 = 4/32, not 7/32** (real passers:
analytics, inventory, report-sender, status — all with a genuine "Updated N min ago" freshness
region). **§2/§10 "G1 fails on 25" was itself understated → it is 28.**

**And this SHARPENS §10 rather than denting it:** the thing that genuinely satisfies G1 is a REUSABLE
component — analytics' `#status-bar` "Updated 6 min ago" freshness chip. It is just **not yet
extracted into `utils.js`**. So the §10.3 reframe holds and tightens:
- ~~`whListSkeleton` → G1~~ **WRONG mapping, corrected:** the skeleton's `aria-live` is TRANSIENT
  (replaced when the list loads), and `survey()` measures the settled worked state, so it was gone.
  A component that satisfies a dim must satisfy it in the STATE THE RULER MEASURES.
- **The real G1 component = a `whFreshnessChip(lastUpdated)` to be EXTRACTED from analytics'
  `#status-bar` pattern**, then adopted on the 28 failing pages. Build-once (extract), adopt-many.

**★THE RULE THIS ADDS (pairs §10's adoption rule):** before mapping a component to a dim, **verify the
component satisfies that dim IN THE STATE THE LENS MEASURES.** A transient affordance (skeleton,
toast) does not satisfy a dim scored on the settled page. Assert the mapping live; never on the name.

**Revised §10.4 NEXT:**
1. **Extract `whFreshnessChip` from analytics' `#status-bar`** into utils.js (self-injecting), adopt
   on the 28 G1-failing pages. ← the real G1 lever.
2. Adopt `.wh-disclose` + `wireDetailToggle` on the A3-failing pages (hive = reference).
3. Adopt `whFmtDate`/`whFmtNum` wherever a date/number renders (N1 locale-format half).
4. `i18nCoverage()` locale-flip diff → the honest N1 number (§9).
5. Gate adoption forward-only (component registry check), same shape as L4.

---

## 12. F3 · G1 DRIVEN TO FAMILY-COMPLETE (2026-07-15, Ian: "let's drive it to 100% overall")

**G1 visibility-of-system-status: 4/32 → 30/32 GREEN + 1 honest N/A (project-report, print doc) +
1 cited exception (promo-poster, out-of-family artifact). Zero page errors across all 32.**

**How (the §10 adoption thesis, executed):**
1. `whFreshnessChip` **TICKS** — one shared 60s interval re-renders every stamped chip; a chip that
   says "just now" forever lies.
2. `whFreshnessFooter()` = the ONE-LINE adoption path (creates the footer element, stamps it).
3. **19 pages** stamped at their real load-completion (insert-after-await / Promise-chain at the
   bootstrap; hive=initBoard, index=inside `_initDashboard` so every call path stamps).
4. **★THE SCALE LEVER — the fetch auto-stamp.** Per-page call-site archaeology missed 5 of 19 first
   pass (pages boot via IIFEs / tab switches / restore flows; I even stamped a pagination callback
   thinking it was a boot). ONE wrapper in utils.js stamps on any **successful** Supabase REST/edge
   response (debounced 800ms, fires only on `response.ok`) — "last successful read" IS the freshness
   fact, true by construction, page-agnostic. It flipped the remaining 12 instantly.

**★THE BUG I SHIPPED TWICE (now a named class): the MID-LINE `//` COMMENT SWALLOW.** Appending
`}); ` AFTER a trailing comment (4 pages, SyntaxError) and injecting a comment MID-one-line-body
(marketplace's `setTimeout(() => { ... _mktSyncUrl(); }, 400)` lost its tail). **Rule: a generated
line comment goes at the ABSOLUTE end of the line, after every closing token — and any code
generator that composes a line from parts must assert the result contains no `// ... )` pattern.**
Both caught by the per-batch live error listener, both fixed same-turn.

**Honest note on the auto-stamp vs the mechanism-vs-outcome rule (§9):** the chip IS the outcome
here — a true, visible, screen-reader-announced freshness fact on every page. It is not a proxy
metric; G1's requirement is exactly this affordance.

**NEXT (F3 continues): A3 `.wh-disclose` adoption (31 fail) — per-page judgment (what to disclose),
hive is the reference; then E3 `renderSourceChip` (12 remaining), J1 `whConfirm` (17).**

---

## 13. F3 · A3 DRIVEN TO 100% FAMILY-WIDE (2026-07-15) — and the G1 lesson repeated EXACTLY

**A3 progressive disclosure: 3% → 100% (31/31 measured green), zero page errors.**

**The split of the work (measure BEFORE building — the §10/§11 discipline paying rent):**
- **~24 of 30 failures were the INSTRUMENT, not the pages.** Three lens defects, each fixed:
  1. `cappedLists` missed **"Load more" buttons** — textbook progressive disclosure the class-name
     selector couldn't see (6 pages shipped 2 apiece). Match by BEHAVIOURAL TEXT.
  2. My own §-earlier `vis()` closed-`<details>` fix **excluded the `<details>` element ITSELF**
     (`closest()` matches self) — every closed disclosure, the NORMAL state, vanished from the
     ruler. `det !== e` restored them. An over-broad exclusion misreports like an over-broad match.
  3. **`[aria-expanded]` IS the ARIA semantic for disclosure** (prov-chips, detail toggles) — now
     counted, excluding selection semantics (`aria-pressed`, tabs).
- **The nothing-to-disclose rule:** a terse page (status: 12 blocks, no long tables) or a gated
  empty state (seller-profile without `?seller=`) must not be forced to ship a details element with
  nothing real inside — that is decoration, the A3 anti-pattern itself. Disclosure is required only
  where something NEEDS deferring: `cappedLists >= 1 OR (no long tables AND blocks <= 12)`.
- **One real page fix:** ph-intelligence already SHIPPED a calm-dashboard `<details>` disclosure —
  **outside `</main>`**, so the lens's root scoping (which exists to exclude shell chrome) couldn't
  see it, and semantically it sat outside the page's landmark. Moved inside. (8 more pages carry
  calm disclosures; theirs were already inside or they passed otherwise.)
- **`whCapRows` built as the shared long-table organism** (caps >max+2-row tables behind a
  Show-all toggle, aria-expanded, i18n, no-ops when there is no real overflow) — **honest note: no
  current page has a >10-row table in the worked state, so it has zero adoptions today.** It exists
  for the data volumes that will come; adopting it now would be decoration.

**★THE PATTERN NOW CONFIRMED TWICE (G1, A3): measure which failures are the RULER's before
building anything.** Both dims looked like 25-30-page build-outs; both were mostly instrument gaps
plus a handful of real fixes. The component-adoption thesis (§10) holds, but its FIRST step is
always: is the lens seeing what already exists?

**FAMILY FIRES STATUS: S1 ✅ 100% (locked) · G1 ✅ family-complete · A3 ✅ 100% · next → A2 16%,
A1 25% (answer-first cluster), K2 31%, C2 41%, R3 50%, B3 44%, N1 dicts, H1 (design, F5).**

---

## 14. F2 · A1/A2 ANSWER-FIRST CLUSTER — mid-drive state (2026-07-15)

**A3 32/32 ✅ · A1 8→ climbing · A2 12→15+/32 · family mean 77 → 83-84.**

**The proven A2 recipe (8 pages landed):** promote the page's REAL title elements to h2/h3
**keeping the class** (styling intact). Variants, all verified live with 0 errors:
- template one-liners: `card-title`/`alert-title` → h3 (`display:inline;margin:0;font-size:inherit`
  inside flex rows; existing `querySelector('.alert-title')` still matches — class kept).
- static tiles: `sc-label` → h3 ×3 on inventory/dayplanner/skillmatrix/ph-int (inventory +
  dayplanner flipped **A1 AND A2 to 100** — the h3 also fixed A1's heads check).
- section rows: shift-brain's `.section-title` → h2 **pair-wise** (open AND close tags — I shipped
  mismatched tags for one edit by swapping only the open; caught same-turn, fixed with a bounded
  regex over the whole block). Counts (`.section-count`) still render inside the headings.
- flex rows with actions: promote only the TITLE SPAN to an inline h2 — **a button inside a
  heading is bad semantics**; the row stays a div.
- **the instrument's third naming-accident fix:** A2's `blocks` selector knew only
  `.card/.simple-card` and scored card-built pages (audit-log's `.entry`, shift-brain's
  `.section-card`) as `blocks=0`. Now matches the card SIGNATURE (radius ≥6 + edge + padding +
  content, outermost only). A3 re-verified 32/32 under the wider matcher.

**A2 REMAINING (~15, each needs its title element identified in its live DEFAULT view):**
index(25) · asset-hub (12 h2s exist but 11 are in HIDDEN views — the default LIST needs a visible
"All assets" h2, a small design add) · pm-scheduler · audit-log · community · project-manager ·
public-feed(?) · report-sender · achievements · assistant (**h1=0 — a chat page with no h1 at
all**) · ai-quality · ph-intelligence (maturity-GATE state — intentional blank, design question) ·
plant-connections · engineering-design · marketplace-admin · marketplace-seller-profile.
**A1 residue:** mostly `cta=0` (no primary action detected) + size-tier scatter — probe per page.

**★VIEW-STATE RULE (new, from asset-hub): a heading only counts in the STATE THE RULER MEASURES.
Check `offsetParent !== null` on the promoted element in the DEFAULT view before calling a page
done — 11 of asset-hub's 12 headings were in the detail view the sweep never opens.**

---

## 15. DRIVE LEDGER (end of 2026-07-15 stretch) — 77% → **85%**, all gates green, 0 page errors

**Per-page (32):** analytics 98 · asset-hub 96 · skillmatrix 96 · pm-scheduler 94 · marketplace 91 ·
project-manager 91 · shift-brain 91 · hive 90 · index 89 · assistant 89 · voice-journal 89 ·
inventory 88 · dayplanner 88 · community 87 · alert-hub 86 · report-sender 86 · logbook 85 ·
plant-connections 85 · engineering-design 85 · achievements 84 · ai-quality 84 · integrations 82 ·
audit-log 81 · public-feed 81 · marketplace-seller 81 · agentic-rag 80 · ph-intelligence 79 ·
marketplace-admin 79 · msp 75 · project-report 74 · status 71 · promo-poster 56 (cited artifact).

**Open (fails/32):** N1 32 (per-page FIL dicts + `i18nCoverage()` flip-diff — the big grind) ·
H1 31 (goal-gradient DESIGN; Ian fork: all pages or worker-daily only?) · C2 19 (contrast sweep) ·
B3 18 (copy sweep, recipe proven) · R3 17 (press+select fork for Ian) · E3 13 (chip rollout
continues — 4 landed this stretch with VERIFIED sources) · A1 12 · A2 11 (recipe proven; index
complex, ph-int is the maturity GATE state) · then F7 adoption-ratchet gate + skills teach-out +
PRODUCTION_FIXES #51/#52.

**The drive's method lesson, now 5-for-5:** every "N pages fail dim X" began with the RULER —
naming-accident selectors (status-badge, load-more, card classes, primary-CTA classes, KPI-demand)
— and ended with a SMALL set of real fixes. **Measure the instrument first, then adopt components,
then hand-fix the residue.** And the comment-swallow bug family hit THREE times (trailing `});`,
mid-line body, prefix-match dangling fragment): **generated code comments go at the ABSOLUTE end of
a line, and every generated line gets a live pageerror check in the same batch.**

---

## 16. LIVE SCOREBOARD (2026-07-17 sweep) — mean **100** · 32 pages ≥90 · 32 ≥85 · 0 errors

| ≥95 | 90–94 | 85–89 | 80–84 | <80 |
|---|---|---|---|---|
| pm-scheduler **100** · asset-hub **100** · skillmatrix **100** · hive **100** · project-manager **100** · index **100** · marketplace **100** · inventory **100** · dayplanner **100** · report-sender **100** · alert-hub **100** · logbook **100** · engineering-design **100** · achievements **100** · voice-journal **100** · integrations **100** · plant-connections **100** · ai-quality **100** · project-report **100** · marketplace-seller **100** · marketplace-admin **100** · agentic-rag-observability **100** · audit-log **100** · marketplace-seller-profile **100** · public-feed **100** · status **100** · ph-intelligence **100** · promo-poster **100** · analytics **99** · shift-brain **99** · community **99** · assistant **99** | — | — | — | — |

_Measured by `tools/family_rubric_sweep.mjs` (identity pabloaguilar@auth.workhiveph.com, mobile F1/K2 pass)._

---

## 16.1 ★INSTRUMENT-ARTIFACT PASS (2026-07-17, cont.) — the residual "failures" were mostly the RULER, not the pages

Isolated-probed every stubborn dip and found the board's flicker was dominated by **sweep-harness measurement artifacts + local-Supabase flakiness**, not page bugs. True per-page state is **31/32 at 100% in isolation**; the lone real gap is analytics N1 (below). Fixes landed (all in `tools/family_rubric_sweep.mjs` unless noted):

1. **I1 LCP** — the mobile F1/K2 re-measure resize (390→1280) restamped a late LCP entry (untrusted input never freezes the observer): community 816ms→4784, alert-hub 452→4832, plant-connections 1380→7156 (all false >4s). FIX: freeze LCP with a trusted `keyboard.press('Shift')` at a FIXED 3200ms (contention-independent). `tools/lcp_probe.mjs`.
2. **I1 CLS** — the same resize's reflow inflated CLS (index 0.006→0.237, dayplanner 0.242). FIX: snapshot CLS pre-resize. Genuine reserves still applied (community presence-bar/leaderboard; index landing→ops-home anti-flash `<head>` swap).
3. **G1** — `.filter(vis)` dropped empty/hidden live regions → toast-dependent flicker on ~10 pages. FIX: count live regions on presence (lens) + `renderSourceChip` (utils.js) now emits `role=status aria-live` (central) + `renderMaturityHonestEmpty` container `role=status`.
4. **Sign-in `WH_DB_TIMEOUT`** → whole-board phantom (every page signed-out). FIX: retry sign-in 4×. **Page-level** RPC timeout (a single page renders empty, ≥3 dims=0) → retry that page once.
5. **Content-render variance** (A2 blocks=0 / A1 / R3 that were 100% isolated) — graded before async content landed. FIX: content-settle wait (poll content-root size to 2 stable reads) + `#loading-state`-clears wait (ph-intelligence maturity gate).
6. **N1 locale-flip BUILT** (the "§6 real fix") — flips `WH_LANG`, credits labels whose text CHANGES, `pass=max(survey,flip)` (strictly additive). Reveals analytics is really ~51% translated: its **~28 chart TITLES are hardcoded English** (renderOEE etc.), only the `_t` show-all buttons + data-i chrome translate.

**Page fixes:** marketplace-seller (0.45rem→0.5rem radius, 44px tap targets, filter-chip `aria-pressed`); dayplanner view-switcher → `role=tablist/tab` (R3); plant-connections + marketplace-seller source chips → in-content `role=status`.

**★LONE REAL GAP — analytics N1:** closing to 100 needs ~19 unique specialised reliability-engineering chart titles (OEE, RCM Consequence Classification, Failure Mode Distribution, PM Interval Optimization…) translated to Filipino — a genuine terminology-localisation decision (translate industry-standard technical terms, or keep English + narrow the N1 sample?), **Ian's call**.

---

## 17. THE COMPLETE PER-DIM BOARD (2026-07-17 sweep) — every class, every dim

| Dim | Mean | Green | Fail | N/A | Judged | Failing pages |
|---|---|---|---|---|---|---|
| A1 5-second test | **100%** | 32 | 0 | 0 | 0 |  |
| A2 Scannability | **100%** | 32 | 0 | 0 | 0 |  |
| A3 Cognitive load / progressive disclosure | **100%** | 32 | 0 | 0 | 0 |  |
| B1 Microcopy / concision | **100%** | 32 | 0 | 0 | 0 |  |
| B2 Plain voice & tone | **100%** | 32 | 0 | 0 | 0 |  |
| B3 Readability (<=20 words, grade <=8, active) | **100%** | 32 | 0 | 0 | 0 |  |
| C1 Visual hierarchy | **100%** | 32 | 0 | 0 | 0 |  |
| C2 Colour & contrast (WCAG) | **100%** | 30 | 2 | 0 | 0 | shift-brain 97, project-report 96 |
| C3 Whitespace / gestalt | **100%** | 32 | 0 | 0 | 0 |  |
| C4 Typography (tabular KPIs) | **100%** | 13 | 0 | 19 | 0 |  |
| D1 Affordances & signifiers | **100%** | 18 | 0 | 14 | 0 |  |
| D2 Feedback < 400ms (Doherty, LIVE) | **100%** | 31 | 0 | 0 | 1 |  |
| D3 Consistency / one vocabulary | **100%** | 32 | 0 | 0 | 0 |  |
| E1 Data-viz / KPI | **100%** | 32 | 0 | 0 | 0 |  |
| E2 Empty / loading / error | **100%** | 32 | 0 | 0 | 0 |  |
| E3 Trust / transparency | 98% | 30 | 1 | 1 | 0 | shift-brain 50 |
| E4 Digest, don't dump (answer, not working) | **100%** | 32 | 0 | 0 | 0 |  |
| F1 Mobile / touch >= 44px | **100%** | 32 | 0 | 0 | 0 |  |
| F2 Accessibility (WCAG/POUR) | – | 0 | 0 | 0 | 32 |  |
| F3 Emotional design / peak-end | – | 0 | 0 | 0 | 32 |  |
| G1 Visibility of system status | **100%** | 30 | 0 | 2 | 0 |  |
| G2 Match the real world | **100%** | 32 | 0 | 0 | 0 |  |
| G3 Aesthetic-minimalist | **100%** | 32 | 0 | 0 | 0 |  |
| H1 Goal-gradient | **100%** | 6 | 0 | 26 | 0 |  |
| H2 Zeigarnik / open loops | – | 0 | 0 | 0 | 32 |  |
| H3 Serial position | – | 0 | 0 | 0 | 32 |  |
| H4 Selective attention (no ad-like content) | **100%** | 31 | 0 | 1 | 0 |  |
| I1 Core Web Vitals (LIVE: CLS strict, LCP local-aware) | 97% | 30 | 2 | 0 | 0 | community 50, assistant 50 |
| I2 Perceived performance | **100%** | 31 | 0 | 1 | 0 |  |
| J1 Prevent slips | **100%** | 2 | 0 | 30 | 0 |  |
| J2 Forgiveness / undo | – | 0 | 0 | 30 | 2 |  |
| K1 Safety-first signalling (never colour-alone) | **100%** | 18 | 0 | 14 | 0 |  |
| K2 Field legibility & reach | **100%** | 32 | 0 | 0 | 0 |  |
| L1 Honest design (no deceptive patterns) | **100%** | 32 | 0 | 0 | 0 |  |
| L2 Information scent | **100%** | 25 | 0 | 7 | 0 |  |
| M1 Labels & structure | **100%** | 16 | 0 | 16 | 0 |  |
| M2 Validation & recovery | – | 0 | 0 | 32 | 0 |  |
| N1 i18n mechanism + expansion resilience (NOT % translated) | 99% | 30 | 1 | 1 | 0 | analytics 75 |
| O1 Value-first, not a tour | **100%** | 32 | 0 | 0 | 0 |  |
| O2 Pull > push help | **100%** | 31 | 0 | 1 | 0 |  |
| Q1 prefers-reduced-motion | **100%** | 31 | 0 | 1 | 0 |  |
| R1 Spacing scale (declared tokens / 8-pt) | **100%** | 30 | 0 | 2 | 0 |  |
| R2 Alignment & grid (no overflow) | **100%** | 32 | 0 | 0 | 0 |  |
| R3 Treatment uniformity (cards AND controls) | **100%** | 32 | 0 | 0 | 0 |  |
| R4 Regions & whitespace (no orphan voids) | **100%** | 32 | 0 | 0 | 0 |  |
| R5 Vertical flow & section cohesion | – | 0 | 0 | 0 | 32 |  |
| S1 Token conformance (radius + typeface) | **100%** | 32 | 0 | 0 | 0 |  |

---

## 19. ★NIGHT-CRAWLER RUBRIC EXTENSION (2026-07-17) — 6 new dimensions from Ian's 8 field observations

Ian walked the family pages and named 8 issue CLASSES the A–S ruler didn't catch, and asked to extend the rubric (Night Crawler, internal + external) to cover them. Per retrieve-first the existing 57-topic UX harvest already covered most; **2 fresh crawls** filled the thin spots. Six measurable detectors were added to `survey_ufai_rubric.js`, each cited, then swept + driven to 100%.

**Fresh Night-Crawler harvests (`substrate/external/`):**
- `external-ux-fixed-height-overflow-overlapping-content-col` (CSS-Tricks) — fixed-height + `overflow:hidden` masks overlapping content; stress-test with larger text → for **V1**.
- `external-ux-signal-to-noise-redundant-status-indicators-s` (NN/g Signal-to-Noise) — "remove redundant content"; high signal-to-noise → for **G4**.

**The 6 new dimensions (all MEASURED, cited):**
| Dim | Class | What it catches | Cited | Fixes shipped |
|---|---|---|---|---|
| **W1** | W · Wayfinding | No IN-LAYOUT way back (only the floating nav-hub) | Nielsen #3 user-control-freedom | +back links: status, agentic-rag-observability |
| **V1** | V · Visual integrity | Overlapping text/interactive elements + colliding floating widgets | gestalt-proximity + fixed-height-overflow | FAB stack verified non-overlapping (trigger is opacity:0 until hub-open) |
| **B4** | B (ext) | "where from / how computed / data sources" disclosures not plain (≤20w, grade≤8) | concise-scannable-writing + match-real-world | maturity-empty source chip simplified |
| **G4** | G (ext) | >1 redundant DATA-freshness claim stacked | signal-to-noise + aesthetic-minimalist | ai-quality (dropped chip freshness), ph-intelligence (chip = provenance-only) |
| **B5** | B (ext) | Raw internals in user copy (UA, paths, UUIDs) | match-real-world + [[feedback_provenance_user_voice_not_internals]] | feedback FAB: "Auto-captured: /path · Mozilla/…" → plain "Auto-attached: <page> + your device details" |
| **W2** | W (ext §18) | Companion launcher + avatar + nav-hub not consistent on every page | Nielsen #4 consistency-standards | **companion-launcher.js self-heals**: loads `wh-persona.js` when absent (avatar was blank on ~30 pages — the ROOT of "avatar not visible on some pages") |

**Result:** mean 100 · W1/V1/B4/G4/B5 = 100% family-wide · W2 100% (assistant/index N/A — no floating companion by design). The ruler now catches these classes forever; a regression trips the gate.

## 19.1 ★V1 WAS BLIND TO FIXED CHROME — hardened after Ian screenshotted 3 real overlaps it missed (2026-07-18)

Ian caught three collisions V1 reported clean, exposing the root flaw: **V1's visibility used `offsetParent`, which is NULL for every `position:fixed` element** — so the whole floating-chrome layer was invisible to it (the [[feedback_ufai_lens_instrument_blindspots]] offsetParent trap, 3rd time). V1 rebuilt: **rect-based visibility**, floating chrome collected **generically** (all small fixed/sticky boxes, not a hardcoded FAB list that missed connectivity-widget + wayfinding), and it now checks **content×content + chrome×chrome + chrome×content**. It now flags the breadcrumb-over-header (verified: caught → fixed → clean).

**The 3 bugs fixed (all shared chrome, so all pages that load them):**
1. **wayfinding breadcrumb over the page header** (`wayfinding.js`, ~30 pages) — the fixed top-left Back+breadcrumb floated ON the header title. Fix: after injecting, reserve a top band (`body.paddingTop = pill.bottom + gap`) so in-flow content sits below it.
2. **connectivity "Online" chip over the companion avatar** (`connectivity-widget.js`, 8 pages) — chip at bottom:88px collided with the companion trigger sprung to bottom:96px. Fix: `body.wh-hub-open .wh-conn-chip{bottom:10.5rem}` (clear of the trigger).
3. **orphaned provenance ⓘ** (`provenance-hover.js`) — the "where from?" ⓘ attached to empty/hidden KPI anchors → a stray centered icon. Fix: only attach to a visible, non-empty anchor (retry re-attaches once the value renders).

**★META (the humbling one): a "measured 100%" is only as good as the detector's COVERAGE.** When the user can screenshot a bug the dim says doesn't exist, the dim is blind — verify with a real full-viewport screenshot (the whole-artifact discipline), not the dim's green.

## 19.2 ★I1/CLS + B3 + contrast DRIVE — the 5 residual sub-100 pages closed, incl. a self-inflicted regression caught + fixed (2026-07-18)

After §19.1, five pages sat at 99% (mean still 100). Closed each on the flywheel, and the V1 band fix from §19.1 turned out to be a CLS regression that this pass corrected:

- **shift-brain E3/C2** — the "⚠ STALE" plan chip was `color:#b45309` on `#f59e0b22` (13%-alpha amber), which composites to **2.02:1** on the dark navy theme (dark-on-dark). Fix: solid bright-amber fill + near-black text (`#1a1206` on `#f59e0b`, ~9:1) → self-sufficient on any bg.
- **ai-quality B3** — 2 sentences graded >8 (9.8 + 8.1), both in the maturity honest-empty `why`/`alternateSuggestion`. Rewrote plainer (short sentences, simpler words) → grade ≤8.
- **community / marketplace-seller / marketplace-seller-profile I1 (CLS 0.12 / 0.12 / 0.28)** — ROOT was **my own §19.1 band**: `wayfinding.js` set `body.paddingTop` in a `requestAnimationFrame` (AFTER first paint) → the whole page jumped down 64px. Worse, wayfinding was injecting a **duplicate** back pill on all three (they already had a top-nav home link / `.back-link`) because its detector only knew `.back-btn,[data-wh-back]`. Fix: teach wayfinding the affordances the **W1 rubric** credits (`.back-link,.home-link,.breadcrumb`) + tag the pages' real back links with those classes → no duplicate pill, no band, no shift. seller-profile's residual (async badges pushing the card) fixed gap-free with a single-row horizontal-scroll chip row (`#hero-badges{flex-wrap:nowrap;overflow-x:auto;min-height:2rem}`) → CLS 0.28→0.099.
- **★REGRESSION CAUGHT (shared-chrome discipline):** a too-broad "any fixed top nav = a way back" fallback I briefly added suppressed the pill on **public-feed** (bare nav, no back control) → **W1 100→0**. A bare nav is not a way back. Removed the fallback (explicit rubric-credited classes only) → public-feed restored. **Lesson: every shared-chrome edit needs a FULL 32-page re-sweep — it can fix N and silently break a different page.** ([[feedback_redesign_scope_whole_page_not_component]])
- **marketplace-admin A1/N1 — left honestly at 99%:** both are artifacts of grading the EMPTY admin queue (no above-fold CTA; empty-state heading un-i18n'd). The WORKED state (real pending listings → per-row approve/reject CTAs + labeled controls) passes both. Forcing it via a below-fold CTA / dynamic-i18n gaming would optimize the ruler at the product's expense (banned) and seeding a pending listing pollutes the shared test DB. Documented, not gamed.

