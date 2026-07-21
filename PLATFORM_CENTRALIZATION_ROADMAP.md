# PLATFORM CENTRALIZATION ROADMAP — the master action plan for a single-source-of-truth platform

**Status:** v0.1 DRAFT for review (2026-07-20) · **Owner:** Ian + Claude · **Type:** the master planning
index for "everything that needs to be centralized," across every full-stack SaaS layer.

> **Why this exists (Ian, 2026-07-20):** *"we have to make a comprehensive roadmap action plan… the
> centralize framework of my platform-wide. everything that needs to be centralized… layout a roadmap
> for every full stack saas layer."* Triggered by the FAB-consolidation session: the nav-hub, companion,
> feedback and connectivity widgets overlapped in the corner AND — once consolidated — turned out to
> **hardcode `#F7A21B` / `Poppins` / radii** instead of consuming `tokens.css`. They were 100% ADOPTED
> yet 0% PURE. That gap is the thing this roadmap makes first-class.

**Relationship to the existing spines (this doc does NOT duplicate them — it indexes + extends):**
- `FULLSTACK_COMPONENT_LIBRARY_ROADMAP.md` = **Axis 1 (Adoption)** spine — "do surfaces USE the canonical?"
  13 layers, P0–P6 template, registries + censuses + ratchet gates for F/A/D/AU/AV. Largely complete.
- `FAMILY_UFAI_ROADMAP.md` = the rubric SCORE board (THE METHOD LAW: a defect on N surfaces = ONE
  unadopted canonical).
- `COMPREHENSIVE_STUDY_FULLSTACK_GATE.md` = the 13-layer × 6-gate test matrix.
- `tokens.css` = the design-token SSOT (primitive + semantic tiers today).
- **THIS doc** = the master index + **Axis 2 (Purity)** + **Axis 3 (Pattern)** — the frontier the FAB
  session exposed, plus the cross-cutting domains the 13 infra layers don't name.

---

## §0 — THE SCOREBOARD (measured %, the anti-drift compass — drive the LOWEST cell)

> Ian, 2026-07-20: *"lay it out with percentage scoreboard per phase, so you won't drift away again."*
> **MEASURED, never asserted** (`feedback_measured_percent_not_qualitative_done`): a % is `done / need`
> with a real denominator; a phase with no denominator yet says "census-pending", not a fake number.
> When unsure what to do next → **drive the lowest %-cell.** Re-measure after every wave.

### Axis rollup (the 3 axes)
| Axis | Measure (denominator) | Current | Target |
|---|---|---|---|
| **1 · Adoption** | layers dispositioned (existing spine) | **13/13** — 5 measured-complete (F/A/D/AU/AV) + 8 governed | 13/13 ✅ |
| **2 · Purity** | shared-code files with 0 raw brand-literals | **20/20 = 100% ✅** · 0 impure (was 106+) · ratchet locked at 0 · full chrome + `utils.js` (platform-wide, 42 lines, renderers live-verified) | 20/20 · 0 ✅ |
| **3 · Pattern** | recurring idioms centralized into a helper | **4/4 = 100% ✅** — `wh-patterns.js` (launchPanel · clickOutside · revealVia · capPanel), adopted in nav-hub + companion, live-verified | 4/4 ✅ |

> **Axis-2 driven to TRUE 100% (2026-07-20, live-verified):** the FULL palette — brand (orange/navy/blue/
> green/red/amber/violet) AND neutrals (—wh-cloud/—wh-steel/—wh-steel-bright/—wh-red-text/—wh-violet-text) —
> across all 16 shared-chrome SSOT files → `var(--wh-*, <fallback>)`. Two waves (87 brand + 19 neutral = 106
> literals → 0). Colors resolve correctly on logbook (hub navy gradient · companion blue · feedback orange +
> cloud text · conn-dot green). Gate `component-purity` registered + ratchet-locked at 0 (fallback-aware +
> purity-allow-aware). The one exempt: voice-handler's JS chart-palette (`purity-allow`, can't resolve var()).

### Purity gap by file (Axis 2 · the C-P2 wave denominator — measured 2026-07-20)
| Bucket | Files | Raw literals | Pure? |
|---|---|---|---|
| Shared chrome | nav-hub (31) · feedback-fab (18) · companion (16) · connectivity (7) | **72** | ✗ |
| Voice/persona | voice-handler (12) · wh-persona (3) | 15 | ✗ |
| Resilience | session-timeout (5) · wayfinding (1) · search-overlay (1) · learn-link (1) | 8 | ✗ |
| Already pure ✅ | offline-queue · form-autosave · device-fingerprint · wh-tts · components.css | 0 | ✅ 5/15 |
| **TOTAL** | **15 files** | **95** | **5/15 = 33%** |

### Per-phase scoreboard (the Purity-first drive — Axis 2 then 3)
| Phase | Measured target (denominator) | Current | % |
|---|---|---|---|
| **C-P0** Census | fallback-aware purity census + registered ratchet gate | `tools/component_purity_census.py` built (fallback+purity-allow aware) · `component-purity` gate registered | **100% ✅** |
| **C-P1** Component tokens | component/motion tokens in `tokens.css` | 8 added: `--wh-z-fab`·`--wh-z-companion`·`--wh-fab-size`·`--wh-fab-gap`·`--wh-panel-max-h`·`--wh-ease-spring`·`--wh-dur-fast/dur/slow` | **100% ✅** |
| **C-P2** Chrome purity wave | 87 → 0 impure · 15/15 files pure | 87→**0** · **15/15 pure** · live-verified (colors resolve) · ratchet at 0 | **100% ✅** |
| **C-P3** Pattern library | 4 idioms → `wh-patterns.js` | 4/4 built + adopted + live-verified + PWA-cached + gated | **100% ✅** |
| **C-P4** Cross-cutting SSOTs | build the registries the evidence WARRANTS (not speculated) | **storage-key SSOT ✅** (real drift: hive-id 3-way + worker 3-way → `storage_key_registry.json` + gate); event-name = **no literal drift** (parameterized); `whToast` = **single-use** (no drift) → neither warranted; shared `<head>`/meta = the one genuine large item, deferred | **storage-key ✅ · rest evidence-dispositioned** |
| **C-P5** Gallery axes panel | live centralization-axes panel in `design-system.html` | **built + live-verified** (Axis-1/2/3 + storage SSOT, reads real baselines: "Axis-2 Purity 100% · 16/16 pure"; 0 console errors) | **100% ✅** |
| **C-P6** All-axes complete | every surface dispositioned by EVIDENCE (done / already-centralized / no-drift / forward-scoped) | **Frontend ✅ ALL 3 axes** (purity 20/20 + patterns 4/4 + adoption) · **RBAC SSOT ✅** · **storage-key SSOT ✅** · backend purity = **already-centralized** (0 hardcode CORS→all import `_shared/cors`; 0 hardcode URL→`Deno.env`) · config/SEO/i18n = **already-governed** · event/toast = **no-drift** · remaining = the gated **convergence adoption waves** (storage drift-aliases → `whHiveId()`/`whWorker()` **DONE v0.4: 149→0 app raw reads**; 17 raw role-checks → `WHRoles.can` = the remaining wave) + shared-`<head>` (SEO-governed) | **all surfaces dispositioned ✅ · adoption waves = gated follow-on** |

**Locking gate (already built):** `validate_fab_consolidation.py` (registered) holds the FAB corner
consolidated. **C-P0's gate** will be `validate_component_purity.py` — a forward-only ratchet: the 95
literal-count may only FALL. That is what makes the scoreboard un-driftable.

---

## ★ THE THREE AXES OF CENTRALIZATION (the reframe)

A platform is "centralized" only when all three hold. The existing spine drove Axis 1 hard; Axes 2–3
are the new work.

| Axis | Question | Direction | Measure | State |
|---|---|---|---|---|
| **1 · ADOPTION** | Do SURFACES use the canonical? | page → component | adopters / surfaces-that-need | ✅ mostly done (F/A/D/AU/AV measured; rest governed) |
| **2 · PURITY** | Is the canonical itself BUILT from the layer below? | component → token/primitive | raw-literals in the canonical (target 0) | ❌ **NEW** — 59 raw brand-hex in the 4 shared-chrome files alone |
| **3 · PATTERN** | Are recurring BEHAVIOURS centralized, not re-coded? | idiom → shared helper | duplicate implementations of an idiom | ❌ **NEW** — reveal-decouple, launcher-defer, panel-cap, click-outside are re-hand-rolled |

**Token tiering (W3C DTCG, already night-crawled):** primitive → semantic → **component** tokens. The
platform has primitive+semantic in `tokens.css`; Axis 2 is the missing bottom-up wiring — the canonical
components must reference the tokens, and high-reuse widgets deserve their own **component tokens**
(`--wh-fab-size`, `--wh-panel-max-h`, `--wh-z-fab`) so their shape is declared once.

**The lever ladder (unchanged, now enforced on BOTH axes):** token → shared component → shared script →
per-page LAST resort. If a value or behaviour is written twice, lift it up a rung.

---

## ★ EXTERNAL EVIDENCE (night-crawled 2026-07-20 — the drive-order question, answered)

Ian asked the Night-Crawler to source reputable external wisdom on how mature platforms sequence
centralization. Four sources distilled into `substrate/external/` (free-tier chain, retrieve-first — the
Google API-design query hit the bag at 0 tokens):

| Source | Contributes |
|---|---|
| **Brad Frost — design-system governance** (`…governance-and-rollout-sequencing…`) | the intake→review→release→adopt LOOP; the **"snowflake vs system"** decision (one-off vs canonical = our exempt-with-reason); a per-component test checklist (a11y/responsive/functional/code+design review) |
| **M. Fowler / Bottcher — platform-as-a-product** (`…platform-as-a-product…`) | **"backlog coupling"**: cross-surface-coupled changes run 10–12× slower → centralize the HIGHEST-coupling surfaces first. The library must be **self-service** (a page adopts without coordinating). |
| **monorepo.tools — SSOT at scale** (`…monorepo-single-source-of-truth…`) | **"enforceable conventions at scale"** = the ratchet gate; **"affected detection"** = a purity census that maps token→consumers; monorepos **amplify AI agents** (full context) — we already are one repo |
| **Azure — multi-tenant architecture** (`…multi-tenant-saas-architecture…`) | tenant≠user; security/scale/isolation per tenant — confirms Layer D (RLS + hive-scoping 100%) is the right centralization for our multitenancy |

**What the evidence DECIDES — the drive order (was the open fork):**
1. **Governance machinery FIRST, then adoption waves** (Frost): build the purity census + component-token
   tier + ratchet gate before mass conversion. Axis 1 already has this shape; Axis 2 needs it — seed =
   `validate_fab_consolidation.py` (built this session).
2. **Prioritize by backlog-coupling reduction** (Fowler): the **shared chrome on ~30 pages is the maximum-
   coupling surface** — one token change today must chase **59 hardcoded copies**. Token-purifying the
   chrome is the single highest-leverage move. → **Axis 2 (Purity) FIRST, starting with the shared chrome**
   — exactly what this session began.
3. **Enforceable conventions** (monorepo): every wave locks a forward-only ratchet; the purity census IS
   the "affected detection" that makes a token change safe.
4. **Snowflake discipline** (Frost): keep exempt-with-reason for genuine one-offs; never force a snowflake
   into the system.

---

## §1 — THE FULL-STACK LAYER LIST (every layer × what "centralized" means × the SSOT × the gaps)

Layers F…AV are the `COMPREHENSIVE_STUDY_FULLSTACK_GATE §4` set (Axis-1 state from the component-library
spine). The `+` rows are cross-cutting domains the 13 don't name but Ian's "encompass everything" needs.

| # | Layer | "Centralized" means | SSOT today | Axis 1 (adoption) | Axis 2/3 gap (NEW work) |
|---|---|---|---|---|---|
| F | **Frontend** | tokens, CSS primitives, JS renderers, shared chrome | `tokens.css` · `components.css` · `utils.js` · nav-hub/companion/etc. | ✅ measured (FCh 100%) | **Axis 2: shared chrome hardcodes 59 hex + Poppins + radii** → consume tokens; add component tokens |
| A | **APIs** | edge-fn `_shared/` modules (cors/ai-chain/ssrf/envelope/tenant) | `supabase/functions/_shared/` (43) | ✅ 100% / 57 fns | Axis 2: do the `_shared/` modules themselves import the base helpers vs re-inline? purity census |
| D | **Database** | RLS/scoping/auth_uid/invoker PATTERNS + `v_*_truth` | `supabase/migrations/` | ✅ 100% / 109 tbl + 49 view | Axis 3: migration idioms (bind-trigger, security_invoker) as generators, not copy-paste |
| AU | **Auth** | identity-restore + session-settle floor | `utils.js` auth floor | ✅ 26/26 | Axis 3: the session-settle/JWT-attach idiom is one helper — verify no re-hand-roll |
| H | **Hosting** | deploy scripts, URL-prefix, cache rules | `PRODUCTION_DEPLOY_RUNBOOK` · deploy-*.ps1 | governed (procedure) | Axis 3: one deploy entrypoint (subst Z:, separate-fn rule) — codify vs tribal |
| C | **Cloud/LLM** | AI chain, prompt patterns, budget guards | `tools/ai_chain.py` · `_shared/ai-chain.ts` | ✅ 27/27 | Axis 2: py mirror ↔ ts source drift gate (already `feedback_python_ai_chain_mirror`) — make it a test |
| CI | **CI-CD** | gate registration, ratchet shape, sentinel wiring | `run_platform_checks` + registration checklist | governed | Axis 3: a validator SCAFFOLD generator so new gates share one shape |
| S | **Security** | escHtml, XSS/CSRF primitives, secret handling | `utils.js` esc floor + security gates | governed | Axis 2: escHtml shim is copy-pasted into widgets (feedback fab has its own) → one import |
| RL | **Rate-Limit** | throttle/debounce + quota envelopes | `_shared/rate-limit.ts` + quota gates | ✅ via A5 | Axis 2: client-side debounce/throttle helper — is there one canonical? census |
| CA | **Caching** | freshness chips, invalidation, warm clients | nav-hub freshness · `_shared/cache.ts` | governed | Axis 3: the getDb() singleton + warm-client idiom — one resolver (partly `_whClient`) |
| LB | **Load-Balance** | pool patterns, load probes | `tools/load_test.k6.js` | governed | infra-procedure; low centralization surface |
| L | **Logs** | logging envelopes, error capture, audit writes | `_shared/logger.ts` + GlitchTip + `hive_audit_log` | ✅ via A8 | Axis 2: client-side console.error → one capture helper feeding GlitchTip |
| AV | **Availability** | offline set (5 scripts) + health | offline-queue/session-timeout/etc. | ✅ 29/29 | Axis 2: the 5 scripts hardcode their own colours/z-index → tokens (this is the FAB fix generalized) |
| +Design | **Design sub-tokens** | motion, iconography, copy, elevation, z-scale | `tokens.css` (partial) · `wh-icons.css` | icons ✅ | **NEW: motion tokens (`--wh-ease`/`--wh-dur`), z-scale adoption, component tokens** |
| +Content/SEO | **Meta / schema / canonical** | one meta+JSON-LD+canonical builder per page-type | per-page `<head>` (drifts) | partial | **NEW: a shared head/meta component + canonical-drift gate (already have the report)** |
| +Analytics | **KPI / event schema** | one event schema + `v_*_truth` KPI defs | `analytics_events` · `v_*_truth` | partial | **NEW: an event-name registry + a KPI-definition SSOT (no magic-string events)** |
| +Notify | **Toast / alert infra** | one toast + one alert-trigger contract | scattered | low | **NEW: a `whToast` canonical + alert-trigger registry** |
| +Realtime | **Subscription patterns** | channel-naming + listener-lifecycle contract | `realtime_subscription_consistency_report` | partial | Axis 3: one `whSubscribe(table, filter)` wrapper (lifecycle + cleanup) |
| +State | **Client storage** | localStorage key registry + offline queue | ad-hoc `wh_*` keys | partial | **NEW: a storage-key registry (prevent `wh_hive_id` vs `wh_active_hive_id` drift)** |
| +i18n | **i18n / copy** | one translation engine + copy SSOT | `utils.js` `_t`/`WH_FIL_PAGE`/`whI18nApply` · `wh_lang` | ✅ FCh3 29/29 | **NEW: a COPY SSOT — error strings + button labels are hand-written per page; marker-without-dict gate already exists, extend to a shared string catalog** |
| +Comms | **email / comms** | one send path + template SSOT | report-sender fn · platform_feedback (Realtime) | low | **NEW: a comms envelope (subject/body/locale) + ONE delivery adapter (free-tier = Realtime, not email — keep the seam) so a 2nd channel is a config, not a rewrite** |
| +Billing | **payments / billing / entitlement** | one pricing + entitlement/tier SSOT | marketplace tables · "stair" gates scattered | partial | **NEW: an entitlement/tier matrix SSOT (stair-gating is inline per feature); pricing tokens; the order state-machine in one place** |
| +Onboard | **onboarding / first-run** | one first-run + empty-state contract | per-page empty states · maturity gate | partial | Axis 3: `whEmptyState()` canonical + a first-run tour registry (substrate already has 2 onboarding harvests) |
| +RBAC | **permissions / roles** | one role→capability matrix | **`wh-roles.js` (window.WHRoles)** SSOT + `role-checks` gate | ✅ AU5 audited · **SSOT built** | **SSOT SHIPPED (2026-07-20): `wh-roles.js` = canonical `role()`/`isSupervisor()`/`can(cap)` + capability matrix mirroring nav-hub tool-roles; live-verified (supervisor can approve, not eng-design). Gate `role-checks` ratchets raw `role==='x'` (18 backlog) forward-only. Convergence of the 18 = follow-on wave. Client UX gate only — RLS is the authority.** |
| +Jobs | **jobs / cron / queue** | one scheduled-task + queue registry | sentinel · trigger-ml-retrain · ingest fns · offline-queue | partial | **NEW: a cron/job registry (schedule + owner + last-run) so scheduled work is enumerable + monitorable, not scattered across fns** |

**Scope expanded 2026-07-20 (Ian: "expand it"):** the 6 rows above (+i18n · +Comms · +Billing · +Onboard
· +RBAC · +Jobs) join the 13 infra layers + 6 earlier cross-cutting domains = **25 centralization
surfaces.** Drive order pending the Night-Crawler harvest (below).

---

## §2 — THE NEW DIMENSIONS Axes 2–3 add (what to BUILD)

1. **A purity census + gate (Axis 2).** `tools/component_purity_census.py`: scan each canonical SSOT
   file for raw literals that a token exists for (brand hex, `Poppins`, off-vocab radii, magic z-index).
   `validate_component_purity.py` = forward-only ratchet (raw-literal count may only fall). The
   `validate_fab_consolidation.py` built this session is the seed shape. Pairs with `validate_design_tokens.py`
   L3 (which already ratchets rawhex on the *glass* — extend it to the *injected JS `<style>`* strings).
2. **Component tokens (Axis 2, DTCG tier 3).** Promote high-reuse shape decisions into `tokens.css`:
   `--wh-fab-size: 56px`, `--wh-fab-gap`, `--wh-panel-max-h: calc(100dvh - 100px)`, `--wh-z-fab`,
   `--wh-ease-spring`. The FAB stack + panel-cap this session hardcoded become one declaration.
3. **A pattern helper library (Axis 3).** `wh-patterns.js` (or fold into utils.js): `whLaunchPanel(openFn)`
   (the stopPropagation+defer launcher idiom), `whRevealClass(el, cls)` (self-contained reveal),
   `whCapPanel(el)` (viewport-cap+scroll), `whClickOutside(el, closeFn)` (the guarded close). Each
   documented GOV.UK-style (when to use / when NOT).
4. **Registries as the connective tissue.** Extend the existing DTCG-shaped registries (`*_component_registry.json`)
   with a `purity` column and a `patterns` registry, so the gallery (`design-system.html`) shows BOTH
   "adopted N/M" AND "pure: yes/no" per canonical.

---

## §3 — METHOD (extends the proven P0–P6 with a purity pass)

Same spine as the component-library roadmap, plus **P0.5 Purity census** after P0 Adoption census, and
**P3 waves now run on BOTH axes** (adopt the canonical on pages; make the canonical pure on tokens).
Retrieve-first (Memento + substrate) · Night-crawl only genuinely-new theory · synthesize into this doc ·
phase + MEASURED % · reuse>extend>build · deepwalk live + lock a ratchet. Token economy is binding: no
fan-out; retrieve what the substrate already harvested (DTCG, atomic design, Style-Dictionary, adoption-
at-scale are all in `substrate/external/`).

---

## §4 — PHASING (the drive order — proposed)

| Phase | Work | Target | Gate |
|---|---|---|---|
| **C-P0** | Purity census across all SSOT files (F chrome first) | measured raw-literal count per file | census runs clean, spot-checked |
| **C-P1** | Component tokens added to `tokens.css` (fab/panel/motion/z) | shape decisions declared once | `validate_design_tokens` extended |
| **C-P2** | **Frontend chrome purity wave** — nav-hub → companion → feedback → connectivity → the 5 AV scripts consume tokens (59 → 0) | 0 raw brand-hex in shared chrome | `validate_component_purity` ratchet |
| **C-P3** | Pattern library `wh-patterns.js` + convert the 4 idioms this session hand-rolled | idioms centralized, re-used ≥2 | pattern registry ↔ census |
| **C-P4** | Cross-cutting new rows: storage-key registry · event-name registry · shared `<head>`/meta · `whToast` | each has an SSOT + gate | per-domain ratchet |
| **C-P5** | Gallery shows adoption + purity per canonical; deepwalk live | dual bars, 0 errors | family ratchet green |
| **C-P6** | Every layer dispositioned on ALL THREE axes; template updated | all rows ≥ target or exempt-with-reason | all gates green |

---

## §5 — NEXT queue (load-bearing on resume — REFRESHED 2026-07-21; the v0.1 queue below it is history)

- **ARC STATE: COMPLETE + LANDED.** C-P0→C-P6 all ✅ (see §0 scoreboard); the three "gated follow-on"
  adoption waves all SHIPPED and landed at `origin/master @ 1ff7193` (2026-07-21): storage convergence
  **149→0** (whHiveId()/whWorker()), RBAC convergence **14→0** (wh-roles.js SSOT, ratchet at 0),
  shared-`<head>` SSOT (favicon 0→32, theme-color unified). Full release gate ALL PASS.
- **SIBLING ARC (2026-07-21): the RULER centralized too** — `UFAI_RUBRIC_CENTRALIZATION_ROADMAP.md`
  applies these same 3 axes to the UFAI rubric toolchain (spec SSOT `ufai-rubric-spec.json` + gates
  `rubric-parity`/`rubric-coverage` + mirror blocks in both lens instruments). All phases ✅.
- **REMAINING (evidence-parked, not active):** a behavioral-kernel codegen for the lens injectables
  (verified regressive — build only if the injectables proliferate); C-P4's comms/billing/jobs rows stay
  governed-forward (no measured drift today — re-census only when a 2nd channel/tier/queue actually lands).
- **Ian-gated:** commit the 2026-07-21 rubric-SSOT work (spec, gates, mirror blocks, coverage board, panel card).

### §5.1 — the v0.1 queue (historical, superseded above)

- ~~IMMEDIATE (C-P0): build `tools/component_purity_census.py`~~ → built + gate registered (v0.2).
- ~~THEN (C-P1→C-P2): component tokens + the chrome purity wave 59→0~~ → 106→0 across 20/20 files (v0.2-v0.3).
- ~~OPEN for Ian's review: 3-axis framing / 25-surface scope~~ → approved; drive executed (v0.2-v0.4).
- ~~Ian-gated: commit FAB work + migration `20260720000002`~~ → landed @ 1ff7193.

## §6 — DRIVE LEDGER
| Date | Delta |
|---|---|
| 2026-07-20 | v0.1 DRAFT. FAB consolidation shipped + verified live (one-FAB corner, tap-collision structurally gone). Purity gap discovered + quantified (59 raw hex in 4 chrome files). 3-axis reframe authored; every-layer table + cross-cutting rows laid out; C-P0…P6 phasing proposed. Grounded in the existing component-library spine (Axis 1) — this doc adds Axis 2 (purity) + Axis 3 (pattern). |
| 2026-07-20 | v0.1a. Forks resolved (Ian): new master doc · scope EXPANDED +6 rows (i18n/Comms/Billing/Onboard/RBAC/Jobs = 25 surfaces). Night-crawled 4 reputable sources (Brad Frost governance · Fowler platform-as-product · monorepo.tools SSOT · Azure multi-tenant; Google API-design hit the bag = 0 tokens, free-tier distill). Evidence RESOLVED the drive-order fork → **Axis-2 Purity first, governance-machinery-then-waves, highest backlog-coupling (shared chrome) first.** `validate_fab_consolidation.py` registered in run_platform_checks. |
| 2026-07-20 | **v0.2 — DRIVE (Ian: "drive to 100% overall, no more stopping"). C-P0→C-P3 to 100% + C-P4 storage-key SSOT, all live-verified + ratchet-locked.** C-P0: `tools/component_purity_census.py` (fallback+purity-allow aware) + `component-purity` gate. C-P1: 8 component/motion tokens in tokens.css (`--wh-fab-size`/`-gap`/`--wh-panel-max-h`/`--wh-z-fab`/`-companion`/`--wh-ease-spring`/`--wh-dur-*`). **C-P2: chrome purity wave 87→0, 16/16 files pure** (`tools/apply_purity_wave.py` converted 70 lines to `var(--wh-*, <fallback>)`; voice-handler palette exempt via `purity-allow`; live-verified colors resolve on logbook). **C-P3: `wh-patterns.js`** (launchPanel/clickOutside/revealVia/capPanel) adopted in nav-hub + companion, live-verified (companion+feedback launch, click-outside close), PWA-cached (sw v163), gated. **C-P4: `storage_key_registry.json` + `validate_storage_keys.py`** (34 keys; 4 drift-aliases tracked: hive-id 3-way + worker 3-way); event-name/toast evidence-dispositioned (no drift). 3 new gates registered. `--fast` re-run in flight to confirm no platform regression. NEXT: rebuild substrate (edited chunked files) → shared-`<head>` refactor · C-P5 gallery purity bars · C-P6 25-surface sweep · neutrals-purity expansion (—wh-cloud/—wh-steel). |
| 2026-07-21 | **v0.6 — shared-`<head>` SSOT wave = the LAST convergence wave (Ian: "go finish all of it"). ALL WAVES DONE.** Measured the 32 app-page `<head>`s: SEO-critical tags (title/description/canonical 28/32/og:title 30/32/JSON-LD) are per-page CONTENT + already gated → stay static (crawlers). Only the brand BOILERPLATE drifted: **favicon linked on 0/32** (assets `favicon.svg`/`.ico`/logo existed but unreferenced) + **theme-color across 3 values** (orange 17 / navy 3 / violet 1). Centralized both via `nav-hub.js` `injectHeadBoilerplate()` (favicon svg+ico+apple-touch + theme-color, if-absent — one source, all 32 pages) + swept the 4 drifted theme-colors → canonical `#F7A21B`. Live-verified logbook: favicon.svg/ico/apple-touch injected + resolve, theme-color `#F7A21B`. Locked into the nav-hub contract gate (`injectHeadBoilerplate` + `favicon.svg` markers). **Adoption waves complete: storage 149→0 · RBAC 14→0 · shared-`<head>` 0→32.** |
| 2026-07-21 | **v0.5 — RBAC convergence: the backlog was INTENTIONAL, not drift (Ian: "yes go").** Deep-triaged the 14 raw `role===` "backlog": each is intentional — member/data fields (`m.role`, `r.role`, report-audience `'worker'`), form/join-flow values (`roleSelect.value`, `joinRole`), role normalizations (`if (role !== 'worker') role = 'supervisor'`), and the deliberately-richer **display-role** derivation (`wh_nav_mode` override `|| HIVE_ROLE`, so a field worker in supervisor nav-mode sees the supervisor view). Converting any to `WHRoles.isSupervisor()` (auth-role-only) would REGRESS behavior. So dispositioned all 14 with `role-check-allow` + specific reasons (zero behaviour change) — the honest convergence. **RBAC ratchet 14 → 0, baseline locked** (new raw role check now FAILs → WHRoles.can()/isSupervisor() enforced). Same lesson as the seed-debt triage: a red backlog that's mostly not real debt. WHRoles SSOT governs new code; index.html live-verified 0 errors after the template-string marker edits. |
| 2026-07-20 | **v0.4 — C-P4 storage ADOPTION big-bang (Ian chose the big-bang sweep).** Built `window.whHiveId()` / `window.whWorker()` canonical accessors in utils.js (read the canonical key, fall back to each registered alias). `converge_storage.py` swept **38 app files**: raw identity-key `getItem` → the accessors, fallback chains collapsed (0 redundant leftovers). **App-page raw identity reads 149 → 0** (residual 31 = test fixtures + utils.js's own definitions, intentional). Live-verified logbook + index: accessors resolve (hiveId=`4eec…`, worker=`Pablo Aguilar`), **0 ReferenceErrors** (the 3 console errors = pre-existing 401s, and their `hive_id` param == `whHiveId()` — proving the converted code passes the right value). Storage-keys gate PASS; its stale "accessor pending" message updated. `--fast` regression sweep in flight. NEXT: shared-`<head>` refactor · RBAC 17-page `role===` → `WHRoles.can` adoption. |
| 2026-07-20 | **v0.3 — DRIVE cont. C-P4→C-P6 + purity expansion to 20/20.** C-P4 storage-key SSOT + gate registered; event-name/toast evidence-dispositioned (no drift). **C-P2 neutrals wave** (+19 literals → 0). **Purity SSOT expanded 15→20 files**: +wh-patterns, wh-help, onboarding, provenance-hover, **utils.js** (platform-wide, 42 lines converted, renderers live-verified: compact-stat red rgb(248,113,113) + action-brief violet resolve). **Whole-artifact discipline caught a REAL break**: provenance-hover's `RUNG_COLOR` map is applied via hex-alpha concat (`color+'22'`), which `var()` can't take — reverted to raw hex + `purity-allow` (new lesson: heed the non-CSS scan flag; alpha-concat + canvas + SVG-attr can't var-wrap). **C-P5 gallery axes panel** built + live-verified (reads real baselines: "Axis-2 100% · 20/20"; 0 errors). Config purity (Supabase URL/key ×46-47 files) = already-centralized via `WH_SUPABASE_URL || fallback` (not a clean drift). All 4 centralization gates green + registered; substrate fresh. **Frontend/shared-code layer: ALL 3 axes 100% + machinery COMPLETE.** NEXT (large multi-session): backend Axis-2/3 (fuzzier — _shared/ module purity) · shared-`<head>`/meta 30-page refactor · RBAC role→capability matrix. (Playwright browser hit ERR_INSUFFICIENT_RESOURCES after the marathon session — a fresh context needed for further live-verify.) |
| 2026-07-20 | **v0.4 — C-P6 +RBAC SSOT shipped.** Real drift found (125 'supervisor' literals, `role==='supervisor'` ×13, isSupervisor computed ×25, NO canonical helper). Built **`wh-roles.js` (window.WHRoles)**: canonical `role()`/`isSupervisor()`/`isEngineer()`/`isField()`/`can(cap)` + capability matrix mirroring nav-hub tool-roles. Client UX gate only (RLS = authority, honoured in the doc). Gate **`validate_role_checks.py`** (registered) ratchets raw `role==='x'` forward-only (18 backlog; nav-hub's role→mode map exempt as the SSOT). Loaded early by nav-hub + PWA-cached (sw). **Live-verified on a FRESH browser context** (fixed the ERR_INSUFFICIENT_RESOURCES): supervisor role read, isSupervisor=true, can('approve')=true, can('engineering_design')=false — matrix correct. 5 centralization gates now green + registered (401 validators). NEXT: backend Axis-2/3 module purity (measure) · the RBAC/storage/purity convergence ADOPTION waves (follow-on) · shared-`<head>` (mostly SEO-governed already). |
