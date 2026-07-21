# UFAI RUBRIC CENTRALIZATION ROADMAP — one ruler, one spec, one kernel

**Status:** v0.2 — DRIVEN (2026-07-21, Ian: *"drive this to 100% overall, no more stopping"*) · **Owner:**
Ian + Claude · **Type:** the action plan to make the UFAI UI/UX rubric a true single-source-of-truth — *the
ruler itself*, the way the last session made the design tokens / components an SSOT.

> **Drive result (2026-07-21):** **Axis-1 Adoption 100%** (32/32 pages, mean 100) · **Axis-2 Purity 100%**
> (spec SSOT + 10 dims/19 canonical floors single-sourced & gate-locked across the lens AND battery,
> live-verified) · **Axis-3 Pattern: contract + data centralized** (verdict classification + thresholds in
> the spec, gate-locked; behavioral helpers verified context-specific-by-design, dedup would regress).
> All work INLINE (Workflow disabled per project rule), gate `rubric-parity` green, live-verified via Playwright.

> **Why this exists (Ian, 2026-07-21):** *"use night crawler for internal and external sources, then you
> can synthesize then lay it out here the roadmap in phases with percentage, and lock it to the header of
> the roadmap so you won't drift."* The handoff scoped this window to **PLAN the centralization of the
> UFAI UI/UX rubric** — *"one canonical rubric + centralized lens instruments, mirroring the design/
> component SSOT pattern just shipped."* We centralized the *tokens the pages consume*; we never
> centralized **the ruler that grades the pages.** This roadmap makes that ruler first-class.

**The core finding (measured 2026-07-21 — the thing this roadmap fixes):** *the rubric is described in one
doc but re-encoded, un-synced, across the toolchain.* **One ruler had three disagreeing dim-counts** — the
doc header said **~49** (frozen at the old A–R total), `survey_ufai_rubric.js`'s header said **44 dims
A–R, v1.0.0**, and the doc BODY had grown to **63 dims across 21 classes (A–W)**. *(The three counts were
reconciled and LOCKED in UR-P0 the same day — see §0; the `rubric-parity` gate now FAILs on any re-drift.)*
The measurable thresholds (≤20 words, FK≤8, 4.5:1, 44px, 8-pt grid, 400ms, >150 rows…) remain **hard-coded
per instrument**, not sourced from one place — the Axis-2 SSOT (UR-P1) still to build.

**Relationship to the existing spines (this doc extends, does not duplicate):**
- `substrate/reference/ufai-ux-rubric.md` = the rubric **prose SSOT** (the cited rules). This roadmap gives
  it a **data twin** every instrument imports, so prose and code cannot drift.
- `PLATFORM_CENTRALIZATION_ROADMAP.md` = the platform's 3-axis SSOT drive (Adoption / Purity / Pattern).
  **This roadmap applies the SAME three axes to the rubric toolchain** — the proven, Ian-approved shape.
- `FAMILY_UFAI_ROADMAP.md` = the rubric SCORE board (the METHOD LAW: a defect on N surfaces = ONE
  unadopted canonical). This roadmap centralizes the **instrument** that produces that board.
- `ufai_battery.js` (`window.__UFAI`, 5 pillars U/F/A/I/C kernel) + `survey_ufai_rubric.js`
  (`window.__RUBRIC`, A–W cited-rule ruler) = the two canonical lenses today.

---

## §0 — THE SCOREBOARD (measured %, the anti-drift compass — LOCKED HEADER, drive the LOWEST cell)

> Ian, 2026-07-21: *"lock it to the header of the roadmap so you won't drift."* **MEASURED, never asserted**
> (`feedback_measured_percent_not_qualitative_done`): every % is `done / need` with a real denominator; a
> cell with no denominator yet says **census-pending**, not a fake number. When unsure what to do next →
> **drive the lowest %-cell** (`feedback_roadmap_percent_is_the_anti_drift_compass`). Re-measure after every wave.

### Axis rollup (the SAME 3 axes as the platform SSOT, applied to the RULER)
| Axis | Question (about the rubric toolchain) | Measure (denominator) | Current | Target |
|---|---|---|---|---|
| **1 · ADOPTION** | Do all sweeps grade against the canonical rubric, and is every dim actually *measured*? | dims encoded as MEASURED detectors / total dims · pages swept / user-facing | ✅ **63/63 dims accounted in ONE board** (`rubric_coverage.json`: 61 single-page + S2/S3 from the corpus) · **pages 32/32 = 100%** (mean 100) · `rubric-coverage` gate locks it | 63/63 · all user-facing ✅ |
| **2 · PURITY (SSOT)** | Is there ONE rubric-as-DATA both the doc AND every instrument derive from? | thresholds sourced from one spec / total · count-parity (doc == code == spec) | ✅ **spec + 3-way gate-lock + 10 dims / 19 canonical floors single-sourced & gate-locked across BOTH the lens and the battery** (mirror blocks == JSON; live-verified) | one spec · counts identical ✅ |
| **3 · PATTERN** | Are the sweep/honesty/DOM idioms centralized, or re-hand-rolled? | shared CONTRACT centralized · behavioral idioms dispositioned | **contract + data centralized ✅** (verdict classification + thresholds declared once in the spec, gate-locked to lens + battery) · behavioral helpers (`vis`/root/settle) = **self-contained-injectable BY DESIGN + verified context-specific** (lens `vis` has 6 `<details>`/offsetParent refs, battery `vis` 1 — dedup would REGRESS) | contract centralized ✅ · code design-constrained |

### Instrument & spec inventory (Axis-2/3 denominators — measured 2026-07-21)
| Bucket | Count | Files | Centralized? |
|---|---|---|---|
| Canonical lenses | 2 | `ufai_battery.js` (__UFAI · 1407L) · `survey_ufai_rubric.js` (__RUBRIC · 1540L) | partial (2 lenses, 0 shared spec) |
| Bespoke batteries | 4 | `companion_battery.js` · `companion_surface_battery.js` · `journey_battery.js` · `analytics_correctness.js` | ✗ each re-embeds kernel bits |
| Sweep harnesses | ~13 | `family_rubric_sweep` · `frontend_ufai_sweep` · `overlay_rubric_sweep` · `live_page_journeys` · `browser_ci_persona_walk` · `perf_scale_sweep` · `run_battery_family.py` · `render_family_scoreboard.py` · `plan_journey_battery.py` · a1/b3/r1 diagnostics | ✗ each re-rolls boot/inject/settle |
| **Stale duplicate** | 1 | `.emoji_bak/survey_ufai_rubric.js` (119 KB, Jul-20 copy) | ✗ literal drift copy → **delete** |
| Rubric-as-DATA spec | **1** ✅ | `ufai-rubric-spec.json` (63 dims · 12 thresholds · owner + verdict + cite per dim) | ✅ **the SSOT, gate-locked** |

### Per-phase scoreboard (Purity-first drive — Axis 2 then 3, then close Axis 1)
| Phase | Measured target (denominator) | Current | % |
|---|---|---|---|
| **UR-P0** Census + parity LOCK | inventory measured + a `rubric-parity` gate that FAILs when doc-count ≠ code-count ≠ spec-count | inventory ✅ · `tools/validate_rubric_parity.py` built + self-tested + **registered** (skip_if_fast:False, fail) · headers reconciled (doc 49→63 · code 44→61) · **green** | **100% ✅** |
| **UR-P1** Rubric-as-DATA SSOT | the N thresholds → ONE `ufai-rubric-spec` module; both lenses import it | **spec ✅** · **3-way parity gate ✅** · **lens single-sources 9 dims ✅** (`RUBRIC_THRESHOLDS` block, live-verified on hive) · **battery I1 CWV value-locked ✅** (`I1_CWV_THRESHOLDS` block == JSON) · **10 dims / 19 floors gate-locked across BOTH instruments** | **100% ✅** |
| **UR-P2** Instrument dedup | delete `.emoji_bak` copy · reconcile the deliberate __UFAI↔__RUBRIC overlap (F1/T1/T2 measured twice) to one owner/threshold | `.emoji_bak` **isolated** (gitignored + untracked + unreferenced → can't drift into build; not hard-deleted — a backup I didn't create) · overlap **canonicalized** in the spec (`owner` + shared threshold per dim; F1/K2 → one `minTapPx:44`) | **dispositioned ✅** |
| **UR-P3** Shared detector kernel (Pattern) | centralize the SHARED contract; disposition the rest by evidence | **honesty-contract centralized ✅** (spec declares each dim's verdict measured/judged; gate `rubric-parity` (3b') locks the lens's M/J tags to it) · thresholds centralized ✅ (UR-P1) · `vis`/root/settle = self-contained-injectable by design, **verified context-specific** (dedup would regress) | **contract centralized + locked ✅ · behavioral dispositioned** |
| **UR-P4** Coverage to 100% | the 2 prose-only cross-page dims (S2/S3) measured by the family sweep · any JUDGED dim made MEASURED where a structure can be built | **pages 32/32 = 100%** (mean 100) · **`tools/rubric_coverage.py` aggregates the 61 single-page dims + S2/S3 → ONE 63-dim board (`rubric_coverage.json`): 63/63 accounted** · **S3 card-parity 94%** (49/52 modal conformance; 4 candidate defects) · **S2 shared-chrome 100%** (W2); registered `rubric-coverage` gate FAILs a source-less dim | **100% ✅** |
| **UR-P5** Rubric-coverage panel | a live coverage/scoreboard panel (mirror `design-system.html` C-P5) reading real sweep output | **UFAI Rubric SSOT card added to `design-system.html` centralization gallery** (fetches spec + scoreboard; **live-verified**: renders "63 dims + 24 thresholds · 32/32 pages · mean 100"; reuses the page, 0 new registration) | **100% ✅** |
| **UR-P6** All-axes complete | every dim dispositioned · all ratchets locked | **63 dims dispositioned** (39 MEASURED · 8 JUDGED-with-reason · 14 NA-capable · S2/S3 cross-page) · gate `rubric-parity` locks set-parity + counts + threshold-values (lens+battery mirror blocks) + verdicts · lens/battery/spec/runner all **verified green** | **100% ✅** |

**Locking gates (what makes the header un-driftable):** **UR-P0's `validate_rubric_parity.py`** — a
forward-only ratchet asserting *doc-dim-count == code-dim-count == spec-dim-count*; a new class added to
the prose that isn't encoded (or vice-versa) FAILs the gate. **UR-P1's spec gate** — every threshold in a
detector must trace to a `ufai-rubric-spec` key (no free-floating literals). These two are the teeth of
"lock it so you won't drift."

---

## ★ THE THREE AXES OF RUBRIC CENTRALIZATION (the reframe — same shape as the platform SSOT)

A rubric toolchain is "centralized" only when all three hold. Today we have strong Axis-1 *coverage* (61/63
dims are measured) but **zero Axis-2 SSOT and zero Axis-3 kernel** — the same asymmetry the platform had
before the last session (100% adopted, 0% pure).

| Axis | Question | Direction | Measure | State |
|---|---|---|---|---|
| **1 · ADOPTION** | Do sweeps grade every dim, on every surface? | dim → detector → page | measured-dims / total · pages-swept / user-facing | ✅ mostly (97% of dims encoded) |
| **2 · PURITY (SSOT)** | Does the ruler have ONE source both prose + code obey? | prose ⇄ data ⇄ detector | thresholds from one spec · count-parity | ❌ **NEW** — 3 disagreeing counts, per-file literals |
| **3 · PATTERN** | Are sweep/honesty/DOM idioms a shared kernel? | idiom → shared module | instruments importing the kernel | ❌ **NEW** — 6 instruments + 13 harnesses re-roll it |

**The lever ladder (same as the platform):** rubric-spec datum → shared detector kernel → per-instrument
override → per-page LAST resort. If a threshold or an idiom is written twice, lift it up a rung.

**The honest exemption class (Brad-Frost "snowflake"):** a dim that is genuinely **JUDGED** (peak-end,
delight — no honest denominator) reports `null`, never an invented number; it stays JUDGED-with-reason and
is *exempt from the MEASURED target, never from being listed in the one spec.* A cross-page dim (S2/S3) is
**owned by the family sweep**, not the single-page lens — that is a declared ownership split, not a gap.

---

## ★ EXTERNAL EVIDENCE (Night-Crawled 2026-07-21 — the "how do mature systems centralize a RULESET" question)

Internal bag first (retrieve-first, 0 crawl): the design-system chunks already answer *how to centralize the
tokens a page consumes* — `external-design-system-governance-and-rollout-sequencing`, `…-adoption-scale`,
`external-design-tokens-w3c-dtcg-format-tiering`, `external-style-dictionary-design-token-pipeline`,
`external-atomic-design-…`. The bag **missed** the specific analog for centralizing a **QA RULESET / lint
config**, so the Night-Crawler teleported out for it (free-tier distill, 3 fresh chunks):

| Source | Contributes to this roadmap |
|---|---|
| **ESLint — shareable configs** (`external-eslint-shareable-config-centralize-lint-rules-si`) | **THE model for UR-P1.** Rules live once in a package that *exports a config object/array*; every consumer `extends` it and *overrides locally after* if needed; the engine version is pinned via `peerDependencies`. → the `ufai-rubric-spec` module exports the dim table; `__UFAI`/`__RUBRIC` `extends` it; a page override sits after; the spec carries its own version. |
| **ESLint — rule severity** (`external-eslint-shareable-config-…rules`) | **`off / warn / error` per rule = the ratchet.** → each dim's `severity` decides gate teeth (informational vs WARN vs FAIL), so a dim can be tightened without touching detector code. |
| **Stylelint — configure / shareable config** (`external-stylelint-shareable-config-design-lint-rules-cen`) | **rules as DATA:** `null | primary | [primary, secondary]`; per-rule `severity: warning|error`, custom `message`, and a `url` to docs. → the exact shape of a rubric-spec datum: `{ threshold, severity, message (fix hint), cite (source url) }`. |
| **W3C DTCG + Style Dictionary** (bagged) | tiering primitive→semantic→component + a transform pipeline from ONE source → the **doc(prose) → spec(data) → detectors** pipeline; the doc becomes the human tier, the spec the machine tier. |
| **Brad Frost — governance** (bagged) | intake→review→release→adopt LOOP + **snowflake-vs-system** → the JUDGED-with-reason exemptions; a per-dim review checklist before a new class enters the spec. |

**What the evidence DECIDES — the drive order:**
1. **Governance/lock FIRST** (Frost): build the parity gate (UR-P0) before mass extraction, so the moment
   prose and code agree they can't silently diverge again. *(Axis-1 already had this shape; the ruler needs it.)*
2. **Purity before pattern** (the platform's own lesson): a shared kernel (P3) is easier once thresholds are
   already data (P1) — extract the SPEC first, then the KERNEL. **Axis-2 is the lowest cell → drive it first.**
3. **Rules-as-data + severity-ratchet** (ESLint/Stylelint): the spec is *data*, and `severity` is how a dim
   tightens without a code edit — the same forward-only ratchet the platform gates use.
4. **Snowflake discipline** (Frost): JUDGED dims and cross-page-owned dims stay declared-and-exempt; never
   fake a MEASURED number to hit 100%.

---

## §1 — THE PHASES IN DETAIL

### UR-P0 · Census + parity LOCK  *(governance-first; the header's teeth)*
**Goal:** freeze the truth and make divergence impossible. **Done when:** (a) this doc's inventory is
committed (✅), and (b) `tools/validate_rubric_parity.py` is registered and green — it parses the class/dim
markers from `substrate/reference/ufai-ux-rubric.md`, the encoded dim ids from `survey_ufai_rubric.js`, and
(after UR-P1) the keys of `ufai-rubric-spec`, and **FAILs on any mismatch** (forward-only). First fix it
forces: reconcile the doc header (~49 → 63) and the code header (44 → 61, note S2/S3 cross-page) so all
three counts agree. **Blast radius:** doc + one gate; no runtime.

### UR-P1 · Rubric-as-DATA SSOT  *(Axis-2 · the lowest cell → drive first)*
**Goal:** one `ufai-rubric-spec` module (`.js` importable by the browser lenses + mirrored/derived for the
Python harnesses) that holds, per dim id: `{ class, title, threshold(s), severity, measured|judged|na,
owner-instrument, cite }`. **Both** `ufai_battery.js` and `survey_ufai_rubric.js` import their numbers from
it (ESLint `extends` shape). **Done when:** every hard-coded threshold in the two canonical lenses traces to
a spec key (census-pending count = the P1 denominator), and the spec gate rejects a free-floating literal.
**Why first:** one token change today must chase ≥2 copies (doc + N detectors) — the maximum-coupling surface.

### UR-P2 · Instrument dedup  *(Axis-2 · kill the copies)*
**Goal:** (a) delete `.emoji_bak/survey_ufai_rubric.js` (a 119 KB stale literal copy); (b) reconcile the
deliberate __UFAI ↔ __RUBRIC overlap where the SAME rule is measured twice with possibly different numbers
(F1 tap-size, T1 content-trapped, T2 text-overflow all live in BOTH) — declare ONE owner per rule or route
both through the P1 spec so the threshold is shared even if the probe runs in both. **Done when:** 0 stale
copies · every double-encoded dim shares one spec threshold.

### UR-P3 · Shared detector kernel  *(Axis-3 · Pattern)*
**Goal:** lift the re-hand-rolled idioms into one kernel the 6 instruments + harnesses import: `vis()`
(the closed-`<details>`/offsetParent-aware visibility test), content-root pick (by content weight), the
MEASURED/JUDGED/NA **honesty contract** (report `null`, never invent), denominator math, and the
boot→inject→settle→run sweep loop (`family_rubric_sweep`'s settle logic is the reference). **Done when:**
instruments-importing-kernel / total = 100%; a new battery is composition, not a copy (atomic-design evidence).

### UR-P4 · Coverage to 100%  *(Axis-1 · close the gap)*
**Goal:** the two prose-only cross-page dims **S2** (shared-chrome parity) + **S3** (card-primitive parity)
are measured by the family sweep (already its job — wire the score into the board); count how many of the
~32 user-facing pages the family sweep actually covers and close to all; any JUDGED dim that a *structure*
could make MEASURED (per the "build-the-structure" doctrine, not "covered-by-nature") gets that structure.
**Done when:** dims 63/63 owned+scored · pages-swept census closed to 100%.

### UR-P5 · Rubric-coverage panel  *(observability — mirror C-P5)*
**Goal:** a live panel (in `design-system.html` or a `rubric-coverage.html`) that reads the real sweep
output + the spec and renders THIS scoreboard — axis rollup, per-dim MEASURED/JUDGED/NA, per-page coverage,
count-parity status — so drift is visible, not just gated. **Done when:** built + live-verified, 0 console errors.

### UR-P6 · All-axes complete
**Goal:** every dim dispositioned; Axis-1/2/3 all green; parity + spec + coverage ratchets all locked at their
floors. **Done when:** the three axis-rollup cells read 100% / one-spec / kernel-adopted and the gates hold them.

---

## §2 — WHAT IS NOT IN SCOPE (so nobody "centralizes" a snowflake later)
- **The prose doc stays the human tier.** UR-P1 does not replace `ufai-ux-rubric.md`; it gives it a machine
  twin. The prose keeps the citations + the *why*; the spec keeps the numbers + severity.
- **JUDGED dims stay JUDGED.** Delight/peak-end have no honest denominator; they are declared in the spec as
  `judged` and excluded from the MEASURED %, never faked to hit 100.
- **Bespoke batteries keep their bespoke probes.** `analytics_correctness.js`'s oracle-parity and the
  companion batteries' surface-specific checks are legitimate specialization; UR-P3 centralizes only the
  SHARED idioms (vis/root/honesty/settle), not the domain probes.

---

_Method: `feedback_ufai_per_dim_measurement_drive` (walk EVERY surface, MEASURED not scored) ·
`feedback_measured_percent_not_qualitative_done` · `feedback_roadmap_percent_is_the_anti_drift_compass` ·
`feedback_redesign_scope_whole_page_not_component`. Cited rules: the 3 fresh + 5 bagged design-system
`substrate/external/` chunks above._
