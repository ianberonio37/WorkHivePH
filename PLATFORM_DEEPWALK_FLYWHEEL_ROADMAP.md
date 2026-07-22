# PLATFORM DEEP-WALK FLYWHEEL — the whole-platform MCP-driven deep-walk arc

**Created:** 2026-07-08 · **Author of directive:** Ian — _"cover my entire platform full-stack SaaS production pages AND AI for my relevant MCPs deep-walk… make it like a flywheel loop."_
**Method:** the same proven engine as ARC DI (`DEEP_WALK_ROADMAP.md §10`), promoted from ONE tier (data-integrity) to the WHOLE platform. `tools/deepwalk_flywheel.py` is the loop driver; this doc is its expanded, sequenced program.
**★★★★ ARCHITECTURAL-LAYER EXPANSION + DRIVE BACK TO 100% — 2154 cells (90 pages × 21 dims + 33 AI fns × 8), 100.0% DRY (2026-07-22, Ian: "organize dimensions by the 13 architectural layers … % per page … centralize … achieve 100% overall").** Grid grew 16→21 page dims: the 6 formerly-blank full-stack layers (A/C/CI/CA/RL/L) were closed CENTRALLY — 5 new per-page cells projecting existing central gates (`D21F` whLogError·L, `D12P` rate-limit·RL, `CP` no-gateway-bypass·C, `CA` NEW sw-shell-membership, `A` edge-fn-auth), CI = meta (the grid IS a page's CI). Two mechanisms: forward-ratchet regex scope (L/A) + gate-emitted pass-list `deepwalk_layer_pages.json` (RL/C/CA, exact invoke scope, no false-credit). Then the two remaining deepwalk fronts closed via ONE central fix each: **D2** (27 ⬜→✅) a gate-accuracy fix in `validate_rpc_write_integrity` (exempt `GENERATED ALWAYS AS IDENTITY`/generated cols — a false-positive that had it locked+FAILING, blocking every D2 cell); **D10** (26 🟡→✅) report-backing `validate_grounding_contract` (55-call/110s deterministic gate exceeded the 90s floor timeout → report-backed with an honest `violations` breach-key). Fixed 3 latent TAG_RE engine bugs (suffix-truncation, letter-dim rejection, `.upper()` mismatch) found while wiring letter-named layer dims. `deepwalk_grid.json` → **✅1244 · 🟡0 · ⬜0 · n/a910 · 46-gate floor · 0 FAIL · grid DRY.** Every fix was CENTRAL (Ian's centralize-first law), not per-page chipping. Committed 04960c8 (layers) + this milestone.

**★★★ SURFACE FOLD COMPLETE — 48 content pages (45 `learn/` + about/privacy/terms) folded → 1672 cells (88 pages), 100.0% DRY (2026-07-08 s2, Ian: "deepen … drive to 100%, no stopping").** Grid MORE THAN DOUBLED from the session-start 784. The static content pages are a DISTINCT surface class (no app shell) bound via a new `content:*` wildcard namespace (so app-only `*` oracles can't false-credit a page they never scanned); only presentation dims apply (D4/D5/D6/D7/D17/D23), app-behaviour dims n/a. Drove all 288 content cells 0 → 240 green + 48 D6: `content:* D23` (plain-language scans 87 pages incl content) + NEW `validate_content_page_hygiene` (`content:* D4/D5/D7/D17`, which CAUGHT + FIXED a real WCAG 1.3.1 heading skip — 5 bare in-content `<h4>` on the platform-overview guide → `aria-level="3"`, live-verified 0 skips in the a11y tree) + `content:* D6` on `cwv_gate` after re-running `cwv_probe.mjs` measured all 49 content surfaces (0 LCP/INP/CLS threshold violations). gate-floor 34 → 38. dry_streak 3/3.

**★★ GRID DEEPENED — 904 cells (40 pages × 16 dims + 33 AI fns × 8), still 100.0% DRY (2026-07-08 session 2, Ian: "deepen the deepwalk arc").** Widened the grid by +3 adversarial page dimensions via shared-mechanism `*` wildcards (the D25/D21 pattern): **D18 destructive-safety** (`validate_destructive_safety` — shared cancellable `whConfirm` modal guards 26 delete/reset sites across 13 pages), **D19 idle-session** (`validate_session_resilience` — singleton client `autoRefreshToken`+`persistSession`+visibilitychange wake-refresh, no stale-401), **D20 resilience** (`validate_client_resilience` — AbortController timeout-bounded `global.fetch` + offline/connectivity widgets). 784 → 904 cells, all 120 new cells green + locked, gate-floor 34 → 37, dry_streak 3/3. Each oracle NEGATIVE-tested (teeth) + **LIVE-verified via Playwright**: whConfirm mounts + Cancel resolves `false` (delete aborts); singleton client `.auth` present; a real authed read returned in 35ms through the timeout-bounded fetch. NEXT deepening frontier: fold the 46 `learn/` pages into the grid (content dims) OR the remaining adversarial dims; keep the floor green.

**★ STABLE RULER = 100.0% — page 100.0% · AI 100.0% (2026-07-08 session 2, Ian: "drive this to 100%, no more stopping").** `deepwalk_grid.json` → **724 ✅ · 0 🟡 · 0 ⬜ · n/a60 · 34-gate floor · 0 FAIL · grid DRY.** Drove **86.8% → 100%** across 4 measured, locked levers, each verified not eyeballed: **(1) D25 PII-egress +33 cells** — registered the already-passing deterministic `validate_redact_iso` (`ai:* D25`) blocking (86.8→89.1, AI 74.7→82.2). **(2) D13 fabrication +26 cells** — CENTRALIZED the CL10 action-faithfulness rail at the ai-gateway egress gated to `ADVISORY_ANSWER_AGENTS` (analytics/project/shift/temporal-rag/asset-brain/assistant/coach; the action-executor agents excluded so their TRUE confirmations aren't stripped), built + teeth-tested + locked `validate_ai_fabrication_contract` (`ai:* D13`: rail-integrity + gateway-centralization + per-fn resolution), live-verified end-to-end through `assistant` (advisory answer preserved, 0 raw fabrication) (89.1→92.7, AI 82.2→94.1). **(3) D3+D22 +80 cells** — promoted the two passing-but-advisory page ratchets `validate_reactivity_wiring`(D3, 7/7 receipts) + `validate_interactive_lineage`(D22, 59 anchors) from `warn`→blocking (the prior session's FORK, resolved by Ian's drive directive) (92.7→98.2, **page 100.0%**). **(4) D10 grounding +26 cells** — made `validate_grounding_contract` reach the containerized python-api (socat sidecar publishing host:8000 + a durable `docker exec` fallback so it can't flap when unmapped): 544/544 read-groups resolve, 0 drift → AI 100.0% (98.2→100.0). D10/D13/D25 are now ALSO covered deterministically in the stable ruler, a stronger outcome than the old "leave them to the flaky live tier" plan. The LIVE-BONUS tier was ALSO driven this session: **25 → 29 proven-ever, 0 breaches** — added 2 clean generator probes (`validate_ai_live_invoke.py` H13/F fmea-populator + H14/F semantic-fact-extractor) via the no-signal short-circuit invariant (structural anti-fabrication: short-circuits before the LLM, 0 writes → no cleanup). REGRESSION-CLEAN: `run_platform_checks --fast` = 454 PASS / 15 FAIL, but all 15 are pre-existing inherited uncommitted-delta (verified NOT from my 5 changed files; they clear on Ian's commit + re-baseline). NEXT (multi-run/cron — live-100% is rate-limit-bounded per session by design, NOT one session): the 3rd generator `intelligence-report` (HARDER — its headline numbers are platform-wide/service-role, so its D13 probe needs a service-role DB-count battery extension, not a short-circuit); live-bonus oscillation to ~31-33 via the nightly `--drive` cron; Streams 1-5 breadth (Stream 5 = the 46 learn/ pages = separate `SEO_AEO_GEO_100_ARC.md`); keep the floor green.

**Status (session 1): STREAM 0 BUILT + DRIVEN 0 → 81.4% (2026-07-08). The v2 whole-platform engine is live (`tools/deepwalk_flywheel.py`): glob-discovers 784 cells, evidence-binds 30 self-tagged validators, runs a 30-gate auto-discovered floor, honest AI applicability (infra fns' D10/D13/D26 = n/a). `deepwalk_grid.json` → coverage **86.8%** (page 92.1% · AI 74.7%) · ✅559 🟡139 ⬜26 n/a60 · 0 gates failed, exit 0. (D26 recall applicability corrected: it's a multi-turn-conversational concern, applicable only to ai-gateway + agent-memory-store — the 22 single-shot task/RAG fns are n/a, not ⬜; +2.8.) Path this session (9 measured, locked jumps): 36.3 (engine+seed) → 54.5 (fold ~15 arcs) → 59.7 (fixed a real cwv coverage regression via the probe) → 70.1 (built `validate_frontend_floor_cells` D17/D15) → 75.3 (+D5 mobile) → 79.6 (built `validate_edge_observed_coverage` D21) → 81.4 (honest AI applicability: infra fns' D10/D13/D26 n/a) → 84.0 (tagged `validate_reactivity_wiring` D3 ⬜→🟡). Live MCP walk verified (analytics.html: authed, 0 console errors, real KPIs). **6th engine delta built: REPORT-BACKED cells** (a tag can name `report=<artifact>`; heavy live oracles are measured by their FRESH report, not re-run in the fast floor) — the mechanism is proven (it correctly CAUGHT a live 403 regression), BUT it must bind only DETERMINISTIC reports: a trial binding of the live-LLM battery `validate_ai_live_invoke` was REVERTED because its report legitimately breaches on env/rate-limit flakiness (403s after an edge-runtime restart), which would flap the stable ruler. The STABLE ruler is at 84.0% (dry on deterministic evidence); the remaining ⬜50 (D13 fabrication + D26 recall) require LIVE edge invocation → the platform's forward-only **LIVE-BONUS tier**, reported SEPARATELY by the flywheel (7th delta `live_bonus_tally`), NOT the stable ruler (binding a flaky live report flaps coverage — proven the hard way). **The live-bonus tier is being DRIVEN UP (not deferred — Ian: "you really are tricky" after an earlier premature stop): 22 → 26 AI cells proven live, 0 breaches, across EVERY AI-fn archetype** — D13 fabrication on Q&A/RAG (asset-brain-query, temporal-rag: nonexistent-entity → abstains, 0 fabricated), orchestrator (ai-orchestrator synthesis), and summariser (hierarchical-summarizer: empty far-past period → no hallucinated digest); D26 multi-turn RECALL (`assistant`, verified BOTH at the reply AND that the turns landed as `agent_memory` rows); + a read-only retrieval-grounding probe (voice-semantic-rag). Battery hardened: runtime hive+asset derivation (anti-seesaw), incremental report checkpoint (survives a slow probe), slow orchestrator probe last. **8th engine delta: FORWARD-ONLY live-bonus RATCHET** (`live_bonus_proven` in the state file = union of every cell ever seen live). Necessary because the free-tier LLM bucket DRAINS across the battery's ~29 sequential probes, so late cells intermittently record rate-limit → the per-run live count oscillates 23-26 (rate-limit NOISE, not regression). proven-ever is the durable metric; it accumulates across runs toward live-100% — so live-100% is **rate-limit-bounded per session** and is reached by accumulation over runs (a nightly `--drive` cron), NOT one session. NEXT (documented grind, multi-run): the remaining generators (fmea-populator, semantic-fact-extractor, intelligence-report) each have an honest empty/grounding contract but WRITE side-effects (probe + cleanup) — bespoke per-fn, ~6-min live verify each; the ratchet accumulates them as they're added. 🟡139 honest partials: D3/D22 (advisory ratchets — promoting them to blocking is a FORK for Ian, not a unilateral call), D25 PII (single-turn only), D10 grounding (live/surface-specific). BONUS: fixed 2 real bugs — cwv coverage regression + `validate_ai_live_invoke` 403'd on EVERY run (persona `leandromarquez` reseeded to hive c19a6094 but battery hardcoded a stale hive → 403 tenancy_denied; diagnosed via postgres MCP, fixed constant + added runtime `_derive_hive()` anti-seesaw → 22 live/0 breaches). DI §10.2 sub-report 100%. **NEXT PHASE (net-new): build DETERMINISTIC per-fn AI oracles OR expand the live-bonus tier; promote advisory D3/D22 gates iff Ian wants them blocking.**

> **The one-paragraph why.** ARC DI proved the pattern: a live MCP-driven deep-walk + fix-to-zero gates + a flywheel that measures coverage, auto-targets the lowest cell, and loops-until-dry drove the data-integrity grid **55% → 100% DRY** in one sitting, objectively. That same loop, widened from the 11 data-integrity classes to **every quality axis** (render-parity, a11y, mobile, perf, security, RLS/tenancy, realtime, and the full AI-risk set) and from the 16-page write-grid to **every production page + every AI surface**, becomes a self-perpetuating platform-quality engine. Not a one-shot audit — a ratcheting loop that leaves the platform measurably higher every cycle and FAILs CI the instant any locked cell regresses.

---

## §1 — The denominator (LIVE-measured 2026-07-08)

The whole-platform grid = **(every surface) × (every oracle dimension)**. The surfaces (workflow-mapped, live-counted 2026-07-08):

| Surface class | Count | Notes |
|---|---|---:|
| **App / tool / landing / legal pages** | **36** | the walkable in-app surface: 27 root write/AI tool pages (240 write+invoke calls) + landings + legal |
| **Learn articles** (SEO/content) | **46** | `learn/index` hub + 45 articles — pure content, no writes/AI (dim-15 only) |
| **User-facing total** | **82** | the primary denominator |
| **Internal / admin / ops** | **+8** | marketplace-admin, founder-console, agentic-rag-observability, llm-observability, architecture, symbol-gallery, validator-catalog, promo-poster → **90 non-test pages deployed** |
| **Edge functions** | **56** | of which **36 are AI** (companion/RAG/voice/agents/orchestrators) |
| **`_shared` AI helpers** | **41** | ai-chain, embedding-chain, observability, tenancy, etc. |
| **Public tables** | **150** | the data floor |
| **On-page AI companion** | ~34 pages | floating `companion-launcher.js` → embed-entry/ai-gateway — so even read-aggregate pages carry an AI touchpoint |

**Scale check:** ARC DI covered a 16-page × 11-class write-grid (~124 cells). The whole-platform grid ≈ **(36 app pages × ~14 page-dims) + (36 AI surfaces × ~9 AI-dims) ≈ 800–900 applicable cells** (learn/ pages collapse to the single SEO dim). An order of magnitude larger — exactly why it must be a **flywheel** (auto-targeted, loop-until-dry, ratcheted, glob-discovered), not a linear audit.

---

## §2 — The oracle dimensions (the axes swept per surface)

ARC DI swept the **write-time** oracle only (D2). The whole-platform deep-walk widens to **~26 dimensions across 6 "oracle-times"** (workflow synthesis). Each cell = (surface × dimension); ✅ only on LIVE MCP evidence + a lock, 🟡 partial, ⬜ open, n/a by evidence. **Canonical rule (from ARC DI): drive the affordance LIVE with the right persona via Playwright → assert at the DATA layer via postgres MCP, never the toast.**

**① WRITE-TIME** — drive a write, assert the row lands + reconciles.
- **D2 Data-integrity** (the 11 DI classes) — **✅ ARC DI 100% DRY** (the baseline this arc builds on).

**② DISPLAY-TIME** — assert what the user SEES == canonical. _The single biggest widening: the 5 read-aggregate pages (analytics, analytics-report, predictive, ph-intelligence, shift-brain) carry NO writes, so DI marks them n/a — display-parity is their ONLY axis._
- **D1 Render-parity (dim-12)** — every rendered value == `v_*_truth` (no stale cache / client re-format / diverged copy). `Playwright + postgres`.
- **D3 Cross-surface receipt** — write-on-A flips KPI-on-B live. `Playwright + postgres`. (DI-6 proved it on the core write pages; breadth to the read pages remains.)

**③ EXPERIENCE-TIME** — the human can actually use it, on any device, with any ability.
- **D4 Accessibility** (axe/WCAG 2.2 AA, keyboard, aria, contrast) · **D5 Mobile/touch/safe-area** (44px, viewport, PWA) · **D6 Core Web Vitals** (LCP/CLS/INP — **0% measured today, highest-value un-swept page dim**) · **D15 Empty/error/loading** (honest gates) · **D17 Smoke** (page loads clean, no console error) · **D22 Deep-interaction** (every modal/tab/filter/wizard/⌘K operates) · **D23 Plain-language** (no jargon in RENDERED copy). `Playwright` (+ axe/web-vitals inject).

**④ ADVERSARIAL-TIME** — an ATTACKER persona drives it, the DB must DENY.
- **D7 XSS/escHtml** (no injection sink) · **D8 RLS/tenant-isolation + BOLA** (cross-hive read → 0 rows) · **D9 BFLA** (worker can't hit supervisor writes) · **D18 Destructive-safety** (delete/reset confirm + no orphan cascade) · **D19 Idle-session** (token-refresh, no stale 401) · **D20 Resilience** (fetch timeout-bounded, 503→graceful, offline-queue). `Playwright (attacker) + postgres (assert denied)`.

**⑤ AI-TIME** — per AI-SURFACE (not per page); invoke live, assert the answer + the boundary.
- **D10 Grounding/retrieval-quality** (cites real hive data, sim floor) · **D11 Prompt-injection** (OWASP LLM01 — resists override/exfil; **Arc R named-open ~66.7%**) · **D12 Cost/quota** (bounded per hive/user/day; **per-surface oracle unbuilt**) · **D13 Fabrication** (no invented action/number — action-fabrication, numeric, schema-hallucination families) · **D24 AI cross-hive isolation + capability-honesty** (OWASP LLM06; owner-only AI tables; refuses cross-hive) · **D25 PII-egress/multi-turn redaction** (LLM06 + PDPA — names don't leak across turns/into stored memory) · **D26 Memory/multi-turn recall** (recalls what was said, abstains when not, and the memory row LANDS). `curl/functions.invoke edge + postgres`.

**⑥ RUNTIME-TIME** — watches all of the above in prod.
- **D21 Observability/SLO** (serveObserved on 56/56 edge fns ✅; **frontend RUM/error-capture is dark** — Arc T frontier). `Sentry + Grafana + Playwright`.

**Real gaps ranked (not owned/closed by any arc yet):** ① **D6 frontend Core Web Vitals = 0% measured** · ② **D21 frontend observability = dark** · ③ **D11 AI prompt-injection** (Arc R open + a RAG IDOR) · ④ **D12 per-surface AI cost oracle** unbuilt · ⑤ **D1/D3 display-parity breadth** on the 5 read-aggregate pages. Everything else has an owning arc + a live gate; the deep-walk's job is **BREADTH** (drive every surface × every applicable dim, loop-until-dry).

---

## §3 — The MCP harness (which MCP verifies which dimension)

| MCP | Status | Serves | Deep-walk use |
|---|---|---|---|
| **postgres** | ✅ connected (JUST FIXED → superuser/BYPASSRLS) | all DB oracles (reads all rows) | `mcp__postgres__query` for every DI/parity/RLS/cost read |
| **docker psql** | ✅ (Bash) | DB **writes** (MCP is read-only tx) | setup/revert/lockout-clear during a walk |
| **playwright** | ✅ connected | live UI persona-walks | operate every affordance; axe/viewport/CWV; realtime 2-tab |
| **crawl4ai** | ✅ (global) | token-cheap page reads | SEO/meta/content sweep of `learn/` |
| **grafana / sentry** | ⚠️ connected, low local fit | observability | GlitchTip is Sentry-read-incompatible; local stack ≠ Grafana |
| **github** | ✅ | PR/commit | end-of-arc commit (Ian gate) |

**Recommended additions (honest fit for a LOCAL Supabase + browser stack):**
- **Supabase MCP** — `get_advisors` (security/perf lints) + `get_logs` (edge/pg/auth) + edge deploy would directly serve dims 9-12. _Fit: marginal-local_ (the CLI `/mcp` endpoint isn't exposed on this version; official server is cloud-oriented → needs a project-ref/PAT, or run the community server against the local DB).
- **chrome-devtools MCP** — network/console/perf traces for dims 1/6. _Fit: skip for now_ (launches a 2nd Chrome → memory pressure; Playwright's console/network + an injected `web-vitals` cover most).
- **lighthouse / axe MCP** — dims 4/6 automated. _Fit: good if a maintained one exists; else inject axe-core + web-vitals via Playwright `evaluate` (already the pattern)._
- **write-capable postgres MCP** — retire `docker psql` for reverts. _Fit: good (a second entry with a write role), low effort._

---

## §4 — The arc streams (sequenced; each a flywheel sub-loop)

Driven top-down; each stream is the flywheel pointed at a surface-class × dimension-band. **Stream 0 is the engine; 1-5 are the coverage frontier.**

- **Stream 0 — FLYWHEEL ENGINE (foundation, mostly built).** Promote `deepwalk_flywheel.py` from the DI grid to a **whole-platform grid** (surfaces × dimensions), live-re-drive the lowest cell via the right MCP each cycle, loop-until-dry, glob-auto-join new validators. _First slice: generalize the grid parser + a `PLATFORM_GRID.md` denominator._
- **Stream 1 — PRODUCTION PAGES × core dims (2/1/3/14).** Every core tool page live-walked for DI (done) + render-parity + cross-surface + empty/error states. _Extends ARC DI's 100% to the parity/state dimensions._
- **Stream 2 — PAGES × UX dims (4/5/6).** a11y (axe) + mobile (viewport) + perf (CWV) live per page. Both viewports, every write page.
- **Stream 3 — SECURITY × (7/8/10).** XSS/escHtml sweep + live RLS/tenant-isolation (2-role) + the fresh **OWASP LLM Top 10** on every AI surface (prompt-injection, data-exfil). Pairs `SECURITY_ADVERSARIAL_ROADMAP.md`.
- **Stream 4 — AI SURFACES × (9/11/12/13).** Every edge fn/agent/RAG/voice invoked LIVE: grounding, cost caps, faithfulness/fabrication, realtime. The AI_UFAI (Arc H) frame, but MCP-driven + flywheel-measured.
- **Stream 5 — CONTENT/SEO × (15).** The 46 `learn/` articles + landings: JSON-LD, canonical, meta, sitemap via crawl4ai. Pairs `SEO_AEO_GEO_100_ARC.md`.

**Sequencing rationale:** Stream 0 first (the ruler), then 1 (highest-value, extends the proven DI work), then 3 (security is risk-ranked highest), then 2 + 4 in parallel-ish, then 5 (content, lowest risk). Each stream loops-until-dry before the next is "started," but the flywheel re-measures ALL streams every cycle so a regression anywhere FAILs.

---

## §5 — The flywheel loop (the engine, generalized)

**Today (v1, built):** `deepwalk_flywheel.py` parses ONE hand-written table (§10.2), runs 6 hard-coded DI gates, names the lowest-coverage page, exits 1 on a gate FAIL. It MEASURES but never itself LIVE-DRIVES, covers PAGES only, and the grid is hand-edited.

**v2 (the extension) — MACHINE-DISCOVERED · EVIDENCE-BACKED · LIVE-RE-DRIVEN · SELF-RE-ARMING.** Small ADDITIVE deltas (do not rewrite the working engine):

- **Grid rebuilt from the filesystem each cycle** → `deepwalk_grid.json`, two sub-grids summed into one number: **PAGE sub-grid** = `glob *.html` (drop static/marketing n/a) × `DI-1..DI-12`; **AI-SURFACE sub-grid** (new) = `supabase/functions/* ∩ ai_seams_catalog.json.ai_fns` (~36) × `AI-1..AI-9` (grounding · no-fabrication · PII-redaction · quota-attribution · tenant-isolation · embed-index · multi-turn-recall · refusal/safety · free-tier-chain). Every AI dim already has a real validator on disk → binding job, not green-field.
- **Evidence-backed cells (kills hand-editing):** each cell's ✅/🟡/⬜ is DERIVED from an oracle that TAGS itself with a one-line header `# DEEPWALK-CELL: <surface-glob> <dim-id>` (e.g. `# DEEPWALK-CELL: logbook DI-2`, `# DEEPWALK-CELL: * DI-1`). The flywheel globs `validate_*.py` + `*_baseline.json`, reads the tag, binds the validator+its latest baseline: **gate PASS / drift==0 → ✅ · report-partial → 🟡 · applicable-but-no-tagged-oracle → ⬜ · untagged validator → `orphan_oracles` nudge.** THIS is the auto-join: a new tagged validator lights its cell next cycle with zero flywheel edits (reuses `validate_auto_discovery.py`'s three globs).
- **The loop (7 steps):** ① DISCOVER (rebuild grid by globbing) → ② MEASURE (derive every cell from its oracle's baseline) → ③ GATE (subprocess every LOCKED gate — the 6 DI + the AI-locked gates; any FAIL → exit 1) → ④ TARGET (lowest-coverage ⬜ cell, tie-broken by blast-radius/severity: DI-5/DI-7/AI-3/AI-5 outrank DI-10/AI-9) → ⑤ **LIVE RE-DRIVE** (`--drive`: Playwright for a page cell / curl+functions.invoke for an AI cell, then the postgres-MCP oracle over row+view+downstream+tenant-boundary, walking §10.5 upstream/downstream to prove no-seesaw; stamp ✅ with row-id+view-delta+ts) → ⑥ PERSIST+EMIT (`deepwalk_grid.json` + `deepwalk_flywheel_state.json`) → ⑦ **LOOP-UNTIL-DRY** (chain the next-lowest cell; if no cell flipped and delta==0, `dry_streak++`; at `dry_streak>=K` (K=3) declare DRY).
- **Convergence + re-arm:** finite (surfaces × dims) matrix, monotonically ratcheted (a ✅ un-sets only via a gate FAIL = a regression to fix, not new work). "DRY" is a resting state, not a terminus: step ① hashes `surface_set_hash` + `oracle_set_hash`; a new page / new AI fn / new tagged validator flips the hash → `dry_streak=0` → the loop re-opens the newly-applicable ⬜ cells automatically. Mirrors the Mega-Gate flywheel-orchestrator (glob members, forward-only ratchet).
- **Two run modes:** default = fast **measure-only** (stays in `run_platform_checks` `skip_if_fast`); a **nightly `--drive` cron** actually re-walks cells live. A `--seesaw-guard` on every re-drive checks the Shared-Truth Register so a cell only flips ✅ when its truth is SSOT-derived / trigger-reconciled+gated — making "dry" trustworthy, not oscillating.

**Per-cycle outputs:** `coverage_pct` (+ `page_pct` + `ai_surface_pct`), `delta_vs_last`, `next_target {surface, dim, oracle, reason}`, `gates_failed[]` (exit 1 iff non-empty), `cells_flipped_this_cycle[]` (with evidence_ref), `newly_joined {surfaces, oracles}`, `orphan_oracles[]`, `dry_streak N/K`. The number is the objective platform-health metric — no eyeballed "done."

---

## §6 — What's already banked (don't re-do)

- **ARC DI — data-integrity: 100% DRY** (register §10.5 + grid 100% + 11 oracle classes + 5 fix-to-zero gates + the flywheel engine). This session.
- **Arc J — realtime: 100%** (2-context subscription/RLS/presence/lifecycle).
- **Q-arc — AI cost/quota caps: done** (per-hive/user/day limiters, 27/27 tables).
- **Arc H (AI_UFAI): partial** — companion/gateway/grounding/fabrication swept deep; the other ~20 AI surfaces only edge-fn-level (the Stream 4 frontier).
- **Fullstack maturity (13 layers): capability-100%** (`COMPREHENSIVE_STUDY_FULLSTACK_GATE.md`) — capability bar met, not per-surface live-walked.
- **MCP harness: postgres MCP fixed + activated; deepwalk_flywheel engine built + registered.**

**★The platform already has ~15 PER-TIER UFAI roadmaps — the flywheel's job is to FOLD them into ONE live-measured loop, not re-audit them.** Each existing arc is a dimension-band already partly swept; its validators glob-join the flywheel's gate-floor, and its open cells become flywheel targets:

| Existing arc doc | Dimension it owns | Folds into stream |
|---|---|---|
| `ACCESSIBILITY_UFAI_ROADMAP.md` | dim-4 a11y | Stream 2 |
| `PERFORMANCE_SCALE_ROADMAP.md` | dim-6 perf | Stream 2 |
| `BACKEND_UFAI_ROADMAP.md` | edge backend | Streams 3/4 |
| `DATA_DB_UFAI_ROADMAP.md` | data/DB (→ ARC DI) | Stream 1 (done) |
| `AI_UFAI_ROADMAP.md` (Arc H) | AI dims 9-12 | Stream 4 |
| `AGENTIC_RAG_ROADMAP.md` | dim-9 retrieval | Stream 4 |
| `SECURITY_ADVERSARIAL_ROADMAP.md` | dims 7/10 | Stream 3 |
| `AUTH_IDENTITY_UFAI_ROADMAP.md` | auth/RLS (dim-8) | Stream 3 |
| `SEO_AEO_GEO_100_ARC.md` | dim-15 SEO | Stream 5 |
| `INTERACTIVE_LINEAGE_ROADMAP.md` / `LIVE_PAGE_JOURNEYS_ROADMAP.md` | dims 1/3 render+receipt | Stream 1 |
| `COMPREHENSIVE_STUDY_FULLSTACK_GATE.md` | 13-layer capability matrix | the coverage skeleton |

So the flywheel is the **unifier**: one grid, one number, one loop, that continuously re-drives every tier's open cells LIVE via MCP and ratchets — replacing ~15 separately-tracked arcs with one self-perpetuating engine.
- _(Detailed per-doc measured-% + per-surface page/AI maps fold in from the `platform-deepwalk-map` workflow.)_

---

## §7 — NEXT queue (fresh window opens here)

**Stream 0 — the engine v2 (build first; 5 small additive deltas to `deepwalk_flywheel.py`, do NOT rewrite it):**
1. `discover_grid()` → build `deepwalk_grid.json` from the 3 globs (`*.html`, `supabase/functions/*`, `validate_*.py`) + the `ai_seams_catalog.json.ai_fns` intersection — replacing `parse_grid()`'s single-table read, SAME weighted-coverage math. Seed dim-2 (DI) from ARC DI (already ✅). → **measures the true whole-platform baseline %** (est. ~85% on the 14-dim average, but the AI + display-parity + CWV cells will read much lower).
2. Add the `# DEEPWALK-CELL: <surface> <dim>` tag convention + the binder (glob validators → read tag → bind baseline → derive ✅/🟡/⬜ + `orphan_oracles`).
3. Add the **AI-surface sub-grid** (AI-1..AI-9) + **DI-12** display-parity, each mapped to the existing on-disk validators.
4. Generalize `DI_GATES` (hard-coded) → "every validator tagged with a LOCKED dim" so AI gates auto-join the down-ratchet.
5. Add `--drive` mode (Playwright for a page cell / curl for an AI cell → postgres-MCP oracle + §10.5 seesaw-guard) + extend the state file with `dry_streak` + `surface_set_hash` + `oracle_set_hash`. Keep default = fast measure-only; a nightly cron runs `--drive`.

**Then loop the streams (flywheel auto-targets; highest-value/highest-risk first):**
6. **Stream 1** — display-parity (D1) + cross-surface (D3) breadth on the **5 read-aggregate pages** (their only axis; biggest single widening).
7. **Stream 3** — the fresh **OWASP LLM Top 10** injection sweep (D11) on the 36 AI edge fns + the D6 **Core Web Vitals** baseline (0% today) + D21 frontend observability.
8. **Streams 2/4/5** — a11y/mobile (D4/D5) per page · adversarial RLS/BOLA/BFLA (D8/D9) · SEO (D15) on the 46 learn/ articles.
9. Each new dim's gate → `run_platform_checks` (grows the flywheel's gate-floor); tag every existing validator so it auto-binds.

**Ian forks (parallel, your gate):** build the client-side embedder (`wh-embed.js`); **commit/deploy the uncommitted ARC DI work** (2 migrations `20260708000001/2` + embed-entry upsert + 6 seeder files + 5 new gates/tools + this roadmap).

_Method per cell (unchanged from ARC DI): map lineage → drive live via the right MCP → run the oracle → flywheel any miss → lock with a gate. A cell is ✅ only on live evidence + a lock; the flywheel re-measures every cycle; loop-until-dry._
