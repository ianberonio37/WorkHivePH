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
| **grid %** | 100 | **·** | 100 | 100 | 100 | **·** | **·** | 100 | **·** | **·** | 100 | **·** | 100 |

**7 layers are grid-measured at 100% per page** (F, D, AU, H, S, LB, AV). **6 layers are BLANK per-page (`·`)** — the
real DEPTH the shallow D1-D10 missed:
- **A (APIs/Edge)** — the edge-fn call path is auth-gated centrally (57-fn gate) but NOT walked per-PAGE (does *this*
  page's `functions.invoke` go through a timeout/error-mapped wrapper + hit only entitled fns?).
- **C (Cloud/LLM) per-PAGE** — D10-D26 are measured on the 36 AI edge-fn SURFACES, but the ~34 pages that carry an AI
  touchpoint (companion-launcher / ai-gateway) have NO per-page AI cell (does *this* page's AI call ground + resist
  injection + not fabricate + not leak PII?).
- **CI** — the gate suite is central but "is this page registered + covered" isn't a walked cell.
- **CA (Caching/SW)** — one `sw.js` shell, but per-page cache-freshness / shell-membership isn't walked (the PWA-
  integrity gate exists; project it into the grid).
- **RL per-PAGE** — 429 handling is central (`whAiError`) + gated, but not a per-page grid cell.
- **L frontend** — `whLogError` backbone exists (utils.js), edge observability is 56/56; **frontend RUM/error-capture
  per page is "dark"** (the roadmap's named Arc-T frontier).

## §3 · Per-page × per-layer matrix (measured)
Full matrix: `PER_PAGE_ARCHITECTURAL_LAYER_MATRIX.md` (90 surfaces, re-generate via
`python tools/derive_layer_deepwalk_matrix.py`). Shape is uniform across app pages:
`F=100 D=100 AU=100 H=100 S=100 LB=100 AV=100 · A/C/CI/CA/RL/L = un-walked`. Learn/content pages carry only the
presentation layers (F/S/LB). This uniformity is itself the finding: the 6 blank columns are a PLATFORM-WIDE gap, so
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

`NEXT: (1) L-frontend — project validate_error_capture into deepwalk_flywheel.py as a per-page D21f cell (whLogError
adoption); it is the highest-value dark layer (frontend observability). (2) RL + CA + C — project the existing
adoption gates (rate-limit-handling, pwa-integrity, no-ai-gateway-bypass) into the grid as per-page cells. (3) A —
audit whether a central whInvoke() wrapper exists; build it if not, then the adoption cell. (4) CI — the registration
cell. Re-run derive_layer_deepwalk_matrix.py after each to watch the blank columns fill. Anti-drift §0; centralize-
first §0.2. All LOCAL; commit is Ian's gate.`
