# HOME DASHBOARD — Full UFAI Rubric drive → `index.html` (Execute arc, drafted for a fresh window)

**Drafted 2026-07-15**, wrapping on Ian's explicit (e): *"I love it, wrap it up, I want to implement this
full UFAI UI/UX Rubric approach to my Home Dashboard Page. we will proceed to next fresh context window."*
This applies the SAME proven method that took the Hive Board (`hive.html`) to **100% compliance** — measure
every UFAI dim live → drive each violation to 100% → verify → score honestly (compliance + quality-curve).

> **TARGET PAGE: `index.html`** — the WorkHive home. It has TWO states: the signed-OUT landing (marketing)
> and the signed-IN **home dashboard** (the "DASHBOARD" section ~line 1057, tool grid, etc.). Grade BOTH
> states, but the dashboard is the focus. Confirm the exact signed-in view on Ground (walk it live).

---

## GROUND (retrieve-first — everything is already banked; do NOT re-derive)

Read these FIRST (they ARE the method — one Read each, or `memento_retrieve.py "<topic>"`):
1. **The ruler:** `substrate/reference/ufai-ux-rubric.md` — **17 classes A–R · ~46 dims**, every rule cited.
   (Class **R · Layout rhythm & spatial harmony** was added 2026-07-15 from the Night-Crawler layout harvest.)
2. **The measurement + honest-scoring method:** memory `feedback_ufai_per_dim_measurement_drive` — grade the
   WHOLE page, every surface/state, MEASURED per-dim; report compliance-100 + quality-curve, never false-100.
3. **The layout-harmony + CLS method:** memory `feedback_layout_harmony_and_view_switch_cls` — class R drive
   (R1 8pt spacing, R3 uniform `.board-card`) + the **view-switcher CLS root-cause** (below, load-bearing).
4. **The whole-page + i18n + color-honesty lessons:** `feedback_lower_cards_rubric_applied_and_verified`,
   `feedback_redesign_scope_whole_page_not_component`, `feedback_proposal_first_ux_mockup_loop`.
5. **Skills (Skill-First):** frontend, designer, qa, mobile-maestro, performance (+ security if forms touch auth).

## THE PROVEN FLOW (repeat exactly what worked on hive.html)

1. **Walk every view/state live** (Playwright MCP): signed-out landing + signed-in home dashboard. Sign in
   as `pabloaguilar` / `test1234` (hive `c9def338-fd73-4b19-8ef1-ee57625953d6`) via the modal at
   `index.html?signin=1`; SET `wh_hive_role='supervisor'` + `wh_active_hive_id` in localStorage (a manual
   sign-in that omits `wh_hive_role` breaks the parse-time reserve → false CLS).
2. **MEASURE per-dim** (live `browser_evaluate`): axe-core CDN inject → C2 contrast %, F2 a11y (target 0/0);
   `getBoundingClientRect` over interactive els → **F1 tap %** (≥44px MIN dimension — width AND height, the
   EN/FIL toggle failed on WIDTH); `font-variant-numeric` on KPIs → C4; `[data-i]` vs translatable text +
   the EN/FIL round-trip → N1; `PerformanceObserver{type:'layout-shift',buffered:true}` → **I1 CLS**;
   distinct inter-block gaps → **R1** (all multiples of 8?); distinct left-edges/widths → **R2**; distinct
   radius/border/bg among peer blocks → **R3**. Build `HOME_DASHBOARD_UFAI_ROADMAP.md` (per-dim % table).
3. **DRIVE each violation → 100% compliance** (the hive.html playbook, all verified there):
   - **I1 CLS:** ★if the dashboard uses a view-switcher (`display:none` panels revealed by JS after init),
     the whole panel inserts late → footer jumps → big CLS. FIX = reserve the view SHELL at `min-height:100vh`
     so the reveal shifts only off-screen content. (hive.html CLS 0.233→0.002 this exact way.)
   - **R1 spacing:** one `#<container> > * { margin-bottom:16px }` 8-pt rhythm; fix inline-margin holdouts at source.
   - **R3 uniform cards:** one `.board-card` (12px radius, uniform border, 14/16px padding) on every peer
     section; flatten inner cards (no card-in-card); let semantic tints override bg only.
   - **N1 i18n (if the dashboard has the EN/FIL toggle):** `window.WH_LANG` + `window._t(en,fil)` +
     a `wh-locale-change` CustomEvent whose listener re-renders dynamic cards from cache (no re-fetch);
     static labels get `data-i` + a WH_FIL entry; audit-style many-string cards get a parallel FIL map.
   - **E3 jargon** (no raw `v_*_truth`/internal terms on glass) · **B1 concision** · **C1/K1/L1
     color-honesty** (red=critical only, adaptive frames, no manufactured urgency) · **E2** honest
     error-vs-empty states · **E1** length-bars not gauges · **D1** 44px + affordances/chevrons ·
     **C4** tabular-nums · **F1** min-WIDTH too.
4. **VERIFY the WHOLE page** (whole-artifact discipline): FULL-PAGE screenshot top-to-bottom (not viewport);
   axe **0/0** in EN AND FIL; gates green (`python validate_no_em_dash.py`, `tools/build_substrate.py`, +
   any home-page regression gate — add one if missing); **0 console errors** (the local `401 v_worker_truth`
   is an expired-token env artifact, not code).
5. **SCORE honestly:** compliance (any cited-rule VIOLATION? → drive to none = 100%) + quality-curve
   (subjective ceiling ~97); report BOTH; a flat-100 on subjective dims is the banned false-100.

## GOTCHAS proven on hive.html (don't re-learn the hard way)
- CLS from a view-switcher = reserve the view shell `100vh` (NOT the inner cards).
- F1 fails on the MIN dimension — a 44px-tall but 35px-wide toggle FAILS; add `min-width:44px`.
- JS-rendered strings need the `_t()` + `wh-locale-change` re-render; static `data-i` swap alone misses them.
- Redesign = whole page: build a CURRENT→TARGET disposition map (KEEP/MOVE/MERGE/DELETE) before implementing;
  a new element that surfaces data X makes every old X-surface redundant → delete/merge in the SAME change.
- Uniform cards (Ian's taste, confirmed): everything a consistent `.board-card`, not lighter/sectioned.
- Night Crawler (`tools/night_crawler.py --watch`) ONLY for genuinely-new harvest gaps (retrieve-first first).

## Gate + commit
Local only; render-budget/em-dash/substrate gates must stay green. Commit/deploy are Ian-gated.
NEXT: fresh window → Ground (read the 5 refs) → walk index.html both states → measure → roadmap → drive → verify.
