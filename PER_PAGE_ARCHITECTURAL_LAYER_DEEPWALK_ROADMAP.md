# Per-Page Architectural-Layer Deep-Walk Roadmap

**Mandate (Ian, 2026-07-22, four directives in one arc):**
1. *"why is it, it still feel like shallow deepwalk dimensions per page?"* — the D1-D10 journey denominator was a
   SHALLOW runtime-flow slice. The real denominator is **D1-D26** (`PLATFORM_DEEPWALK_FLYWHEEL_ROADMAP.md`), and the
   right ORGANIZATION is by **architectural layer**, not flow-class.
2. *"organize your dimensions according to the architectural layers of my platform"* — re-project the deepwalk
   dimensions onto the **13 full-stack SaaS production layers** (`COMPREHENSIVE_STUDY_FULLSTACK_GATE.md` §4).
3. *"update the roadmap with percentage completion each dimension per page with anti drift discipline"* — a MEASURED
   per-page x per-layer % matrix, derived (not hand-counted), with anti-drift rails.
4. *"if there is something to centralize, do it, because I don't want that we have to chip page by page all the time"*
   — the METHOD LAW is a first-class rail: a low layer-% across N pages is ONE unadopted central component, never N
   per-page fixes. Most depth-gap layers ALREADY have a central component; the work is per-page MEASUREMENT of its
   adoption, not per-page chipping.

**Source of truth:** `deepwalk_grid.json` (the flywheel's 1704 page x D-dim cells) re-projected by
`tools/derive_layer_deepwalk_matrix.py` (deterministic, re-runnable) into `PER_PAGE_ARCHITECTURAL_LAYER_MATRIX.md`.

---

## §0 · ANTI-DRIFT DISCIPLINE (read first, every session)
1. **MEASURED, never qualitative.** Every page x layer % comes from `derive_layer_deepwalk_matrix.py` over the grid
   (✅=1.0, 🟡=0.5, ⬜=0, n/a excluded). No hand-counts. Re-run it; don't eyeball.
2. **★CENTRALIZE-FIRST is the LAW (Ian's directive #4).** Before touching a page, ask: *"is this layer's dimension a
   CENTRAL component every page should adopt?"* If a layer scores low on N pages, the fix is ONE canonical component
   (a `utils.js` helper, a shared `sw.js`, the ai-gateway, a standing gate) adopted platform-wide, and a per-page gate
   that MEASURES adoption — **never N per-page edits.** The depth-gap layers below mostly ALREADY have their central
   component; the work is the per-page adoption CELL, not the fix. [[feedback_ufai_lens_instrument_blindspots]]
3. **LIVE-CONFIRM + GATE every fix** — a discovered gap becomes a registered `validate_*` (Hardening Loop); a fix
   without a gate is undiscovered debt. Adoption gates are forward-only ratchets.
4. **A per-page cell is ✅ only on EVIDENCE** — a standing gate that mechanically asserts the central component's
   presence on that page, OR a live MCP walk recorded in the flywheel grid. "Probably adopted" is ⬜ until measured.
5. **RE-VERIFY the gate suite after each layer** — enumerate EVERY `--fast` FAIL line (the under-review lesson);
   rebuild the substrate after any doc/central-file edit.
6. **MOMENTUM** — the next un-walked layer cell is the known unit; only (a) fork (b) external ceiling (c) irreversible-
   sole-item (d) matrix genuinely 100% (e) Ian-says-wrap ends a turn. Commit/push = Ian's gate → pivot.

## §1 · The 13 architectural layers × their deep-walk dimensions (the ORGANIZATION)
Re-projected from D1-D26. `[central]` = the canonical component that a per-page adoption cell measures.
| # | Layer | Deep-walk dimensions (D#) | Central component `[central]` |
|---|-------|---------------------------|-------------------------------|
| **F** | Frontend | D1 render-parity · D3 cross-surface receipt · D4 a11y · D5 mobile · D15 empty/error/loading · D17 smoke · D22 deep-interaction · D23 plain-language | `utils.js` shared UI (whListSkeleton/whModalA11y/whClickableKbdA11y/…) + the view-aware/restore/dedup branches |
| **A** | APIs/Edge | *(gap)* edge-fn call resilience + auth-in-flow + status/body contract | edge-fn-auth-gate (57 fns) + a `whInvoke()` timeout/error wrapper `[to measure per-page]` |
| **D** | Database | D2 data-integrity (11 DI classes) | RLS + attribution-pin trigger + OC guards + dedup indices |
| **AU** | Auth | D19 idle-session (token-refresh, no stale 401) | singleton `getDb()` autoRefreshToken + visibility wake-refresh |
| **H** | Hosting/Multitenancy | D8 RLS tenant-isolation + BOLA · D9 BFLA | RLS policies + `resolveTenancy`/`whHiveId()` + supervisor-approval-backstop |
| **C** | Cloud/LLM | D10 grounding · D11 prompt-injection · D13 fabrication · D24 AI cross-hive · D25 PII-egress · D26 memory-recall | the ai-gateway (ONE front door) + no-ai-gateway-bypass + `whAiError` |
| **CI** | CI-CD | *(gap)* per-page gate registration + coverage | `run_platform_checks` + the Unified Mega Gate `[to measure per-page]` |
| **S** | Security | D7 XSS/escHtml (+ SAST/OWASP) | `escHtml`/`escJsAttr` + innerHTML-audit gate + SAST |
| **RL** | Rate-Limit | D12 AI cost/quota (per hive/user/day) + 429 UX | `_shared/rate-limit.ts` + `whAiError` 429 mapper + rate-limit-handling |
| **CA** | Caching/CDN | *(gap)* SW/PWA cache freshness + shell-file versioning | ONE `sw.js` SHELL_FILES + cache-version bump `[to measure per-page]` |
| **LB** | Load/Perf | D6 Core Web Vitals (LCP/CLS/INP) + render-budget | `cwv_gate` + render-budget ratchet |
| **L** | Logs/Observability | D21 edge observability + *(gap)* frontend error-capture | `whLogError` backbone (utils.js) + serveObserved (56 fns) `[frontend RUM to measure per-page]` |
| **AV** | Availability/Recovery | D18 destructive-safety · D20 resilience (offline/timeout/503) | shared `whConfirm` + AbortController fetch + `offline-banner.js` |

## §2 · MEASURED coverage — per-layer platform-wide % (from the grid, app pages)
| Layer | F | A | D | AU | H | C | CI | S | RL | CA | LB | L | AV |
|-------|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **grid %** | 100 | 100 | 100 | 100 | 100 | 100 | meta | 100 | 100 | 100 | 100 | 100 | 100 |

**★ ALL 13 layers now grid-measured (2026-07-22): 12 layers at 100% of applicable pages + CI = meta.** The 6
formerly-blank layers were closed CENTRALLY (one adoption cell each, projecting an EXISTING central gate — no
per-page chipping), then the two deepwalk fronts that remained (D2 data-integrity, D10 grounding) closed via two
single-gate CENTRAL fixes → **grid 100% overall.** How each formerly-blank layer closed:
- **A (APIs/Edge)** — `A` cell via `validate_edge_fn_auth_gate` (57 fns), scoped to pages with `functions.invoke`
  (`has_edge`); 13 ✅ / 77 n-a.
- **C (Cloud/LLM) per-PAGE** — `CP` cell via `validate_no_ai_gateway_bypass`, gate-emitted pass-list of the 12
  AI-invoking pages; 12 ✅ / 78 n-a (observability pages that only MENTION an AI fn = n-a, not false-✅).
- **CI** — META, no distinct cell: the grid ITSELF is the page's CI coverage (every green cell is a gate CI runs);
  a separate CI dim would be circular.
- **CA (Caching/SW)** — `CA` cell via NEW `validate_sw_shell_membership`, pass-list of the 8 SW-shell pages;
  8 ✅ / 82 n-a.
- **RL per-PAGE** — `D12P` cell via `validate_rate_limit_handling`, pass-list of the same 12 AI-invoking pages;
  12 ✅ / 78 n-a.
- **L frontend** — `D21F` cell via `validate_error_capture` (`whLogError` adoption), scoped to backend pages
  (`has_backend`); 35 ✅ / 55 n-a. Arc-T frontier now measured.

## §3 · Per-page × per-layer matrix (measured)
Full matrix: `PER_PAGE_ARCHITECTURAL_LAYER_MATRIX.md` (90 surfaces, re-generate via
`python tools/derive_layer_deepwalk_matrix.py`). Shape across app pages (2026-07-22, all layers closed):
`F=D=AU=H=S=LB=AV=100` (all app pages) `· A/C/CA/RL/L = 100 of applicable pages (scoped, rest n-a) · CI=meta`.
Learn/content pages carry only the presentation layers (F/S/LB). The former uniform-blank finding — the 6 blank
columns were a PLATFORM-WIDE gap — is now RESOLVED: each was closed by ONE central adoption cell, so
per §0.2 they are closed CENTRALLY, not page-by-page.

## §4 · WORK QUEUE — close the 6 blank layers CENTRALLY (one adoption cell per layer, not per-page chipping)
Each is a per-page ADOPTION gate over an EXISTING central component (the component is built; the cell measures it):
| Layer | Central component (exists?) | Per-page cell to add (the measurement) |
|-------|-----------------------------|----------------------------------------|
| **L** frontend | ✅ `whLogError` (utils.js, error-capture backbone) | `validate_error_capture` projected into the grid as `*|D21f` — every page's caught-error paths route to whLogError |
| **RL** per-page | ✅ `whAiError` + rate-limit-handling gate | project rate-limit-handling into the grid as `ai-touch|D12p` per AI-carrying page |
| **CA** | ✅ ONE `sw.js` SHELL_FILES | project PWA-integrity into the grid as `*|CA` — page in shell + cache-versioned |
| **C** per-page | ✅ ai-gateway + no-ai-gateway-bypass + whAiError | `*|Cp` — every AI-carrying page's call goes through the gateway (no direct fn call) + handles 429 |
| **A** | ✅ edge-fn-auth-gate; ⬜ `whInvoke()` wrapper | build the central `whInvoke()` (timeout + error-map) IF missing, then `*|A` adoption cell |
| **CI** | ✅ run_platform_checks | `*|CI` — page is in PUBLIC_PAGES + has ≥1 registered gate |

**Method per layer (centralize-first):** (1) confirm the central component exists (most do); (2) if a page-level
adoption gate exists (error-capture, rate-limit-handling, PWA-integrity, no-ai-gateway-bypass), PROJECT it into
`deepwalk_flywheel.py`'s dimension set as a new `*` wildcard cell so the grid MEASURES it per page; (3) only where no
central component exists (e.g. a `whInvoke()` edge wrapper, frontend RUM) BUILD the one component + its adoption gate;
(4) drive the new column to 100% by ADOPTION, ratchet it. This adds ~6 columns x ~34 app pages ≈ 200 new measured
cells WITHOUT per-page chipping — the fix is central, the grid just starts scoring it.

## §5 · EXECUTION RESULTS — 5 of 6 blank layers now MEASURED in the flywheel (Ian: "yes go ahead")
Each layer is a NEW per-page cell in `deepwalk_flywheel.py`, projecting an EXISTING central component's gate
(centralize-first: no per-page chipping — the grid just starts scoring adoption). Two clean mechanisms emerged:
- **regex applicability** for a FORWARD-RATCHET gate (covers all pages of a kind): **L** (`D21F`, whLogError via
  `validate_error_capture`, scoped by a `has_backend` page signal) + **A** (`A`, edge-fn-auth via
  `validate_edge_fn_auth_gate`, scoped by a `has_edge` = `functions.invoke` signal). No over-match (the ratchet
  genuinely covers every page of that kind).
- **gate-emitted PASS-LIST** for a gate with precise invoke/exemption scope (a regex would false-credit): the gate
  writes its EXACT covered pages to `deepwalk_layer_pages.json`, the flywheel reads it. **RL** (`D12P`,
  rate-limit-handling → 12 AI-invoking pages) + **C** (`CP`, no-ai-gateway-bypass, same 12) + **CA** (`CA`, NEW
  `validate_sw_shell_membership` → the 8 SW-shell pages). This CORRECTLY excludes the observability pages that
  MENTION an AI fn without invoking it (llm-observability|D12P = n/a, not a false ✅).
- **CI** needs NO distinct cell — it is META: the grid ITSELF is the page's CI coverage (every green cell is a
  gate that CI runs on that page). A separate `CI` dim would be circular. Documented, not forced.

**3 latent flywheel ENGINE bugs fixed while wiring these** (each would have broken any non-D#-numeric dim):
`TAG_RE (D\d+)` truncated suffixed dims (D21f→D21) → `(D\d+\w*)`; then `(D\d+\w*)` still rejected layer dims
(CA/CP/A start with a letter, not D+digit) → `([A-Z][A-Z0-9]*)`; and the tag dim is `.upper()`'d so lowercase
suffixes never matched → uppercase-consistent naming (D21F). All backward-compatible (D1/D6/content:*/ai:*/report=
unchanged, unit-tested).

**VERIFIED + COMMITTED (2026-07-22, commit `04960c8`):** all 5 layers land clean, no ruler flap —
`D21F 35✅/55n-a · D12P 12✅/78n-a · CP 12✅/78n-a · CA 8✅/82n-a · A 13✅/77n-a`. The pass-list
mechanism (`deepwalk_layer_pages.json`) correctly scopes each (`llm-observability|D12P = n/a`,
`marketplace|CA = n/a` — no false ✅). The `validate_sw_shell_membership` CA gate was registered in
`run_platform_checks` so the flywheel runs+locks it (🟡→✅).

## §6 · DRIVE TO 100% overall — two CENTRAL gate-accuracy fixes closed the whole grid (2026-07-22)
After the 6 layers, the grid had exactly two open fronts, BOTH closable by a single central fix each
(centralize-first — no page-by-page chipping):
- **D2 (data-integrity, 27 ⬜ pages) → ✅ via ONE gate-accuracy fix.** The 27 cells were ⬜ because their
  bound `* D2` wildcard oracle `validate_rpc_write_integrity` was locked+**FAILING** (flywheel: locked-fail →
  ⬜+regressed). The "failure" was a FALSE POSITIVE: its required-column query filtered only `column_default
  IS NULL`, so a `GENERATED ALWAYS AS IDENTITY` column (NOT NULL, no default, yet DB-auto-populated —
  `snapshot_db_size.id`) was wrongly flagged as an INSERT omission. Fix: also exempt `is_identity='YES'` +
  `is_generated='ALWAYS'` (auto-populated cols the DB fills itself; a real app-supplied NOT-NULL col still
  keeps `is_identity='NO'` so genuine omissions are still caught). Selftest extended with an identity-column
  fixture. Result: 304/304 fns PASS → **27 D2 cells ⬜→✅, page 97.4%→100.0%, gate-floor 0 FAIL.**
  ([[feedback_red_gate_may_be_inaccuracy_not_backlog]] — a RED gate can be gate INACCURACY, not a backlog.)
- **D10 (grounding, 26 🟡 AI fns) → ✅ via report-backing.** The cells were 🟡 because `validate_grounding_contract`
  makes 55 live `/calculate` calls (docker-exec fallback, ~110s) — over the flywheel's 90s `run_gate` timeout →
  SKIP → 🟡. It is DETERMINISTIC (544/544 read-groups resolve, 0 drift — NOT the rate-limited live-LLM tier), so
  the roadmap's report-backed-cell mechanism is the designed fix: emit a `violations` breach-key mirroring the
  FAIL condition (honest), tag `ai:* D10 report=grounding_contract.json`; the floor reads the fresh report
  (instant) instead of re-running. Result: report regenerated fresh (544/544=100%, 0 drift, `violations:[]`) →
  **26 D10 cells 🟡→✅, AI 94.1%→100.0%.**

**★ GRID 100% (2026-07-22, VERIFIED): coverage 100.0% · page 100.0% · AI 100.0% · 2154 cells → ✅1244 🟡0 ⬜0
n/a910 · gate-floor 46 gates 0 FAIL · grid DRY (NEXT TARGET: none).** Both closes were CENTRAL single-gate
fixes (Ian's centralize-first law), NOT per-page chipping: one query-accuracy fix flipped 27 D2 cells; one
report-backing flipped 26 D10 cells. Every applicable cell across all 90 pages + 33 AI fns × the full
dimension set is now measured-✅ or honest-n/a.

`NEXT: rebuild substrate + commit the drive-to-100% milestone (Ian's gate → pivot, don't stop on it). The grid
is DRY; forward hygiene = keep the floor green + the nightly --drive cron refreshing report-backed cells (the
grounding report re-freshes on any full gate run within its 14-day window). Live-bonus tier (32 proven-ever,
forward-only ratchet) accumulates via the cron, NOT a per-session target.`
