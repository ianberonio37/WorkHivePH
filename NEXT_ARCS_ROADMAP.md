# NEXT ARCS — PROGRAM ROADMAP (live-persona-walk, MCP-verified)

**Created:** 2026-06-30 · **Owner:** Ian + Claude · **Status: DRAFTED — awaiting fresh-window execution.**
**Sequence (Ian-chosen 2026-06-30):** ① Forward-Build Backlog → ② Arc R (Security) → ③ Arc U (Accessibility) → ④ Arc T (Observability). Then wrap.

> **Why this doc exists.** The per-tier UFAI series (Arc D→J) and the experience/correctness series (K·S·V·W·X·Y + Interactive Lineage) are **done**. What remains is three un-swept dimensions + a cross-cutting live-exercise backlog. This is the **program-level sequencer**: it sets the order, defines the shared **live-persona-walk verification harness**, and points each stream at its detailed spine (existing or to-be-drafted at that stream's window-open). Each stream still follows the platform's standing discipline: **study-first (mine the denominator, never estimate) → build → live-verify EACH phase → ratchet a measured-% board → forward-only CI gate → skill+memory writeback.**

---

## §0 — THE STANDING VERIFICATION DOCTRINE (applies to every stream)

Ian's instruction (2026-06-30): *"live playwright MCPs diverse persona each, or any MCPs appropriately."* Every phase of every stream is proven by **walking the live platform as a DIVERSE set of personas**, not by a static gate alone. The gate ratchets; the **persona walk is the evidence**.

**The rule (reinforces [[feedback_playwright_live_every_phase]] + [[feedback_deep_mcp_walk_every_page]]):**
- **LIVE every phase, not batched to a capstone.** Each phase: persona walks the real surface at `127.0.0.1:5000` (signed in via the real JWT identity), operates every affordance, creates REAL records, and the result is VERIFIED at the data layer (postgres MCP / `docker exec psql`) — not just "the UI didn't error."
- **Diverse personas per phase.** Each stream declares its persona roster (below). A phase isn't done until each relevant persona has walked it and the floor held for all of them.
- **Reuse the harness, don't rebuild.** `tools/effortless_sweep.mjs` / `tools/live_page_journeys.mjs` already do sign-in-once → per-page audit → ratchet. Persona walks extend that recipe + Playwright MCP for the interactive/adversarial steps. (Don't reinvent — see [[reference_playwright_mcp_reuse_mega_gate]].)
- **MCP-by-fit.** Playwright MCP = the live browser walk (all streams). postgres MCP = verify isolation/state at the DB (R + Forward-Build). Grafana + Sentry MCP = observability assertions (T). github MCP = CI/PR for the env-frontier (Forward-Build #7).
- **Browser-lock discipline:** if the Playwright MCP browser locks, ask for a restart — don't thrash ([[feedback_playwright_mcp_dont_inject_signin_instead]]). The `_id`-seeded service-role client is the standing 2nd-context substitute for a second live UI.

**The shared persona pool (role-diverse, reused across streams):** ① *Field technician* (mobile, gloved, hurried, low-literacy) · ② *Supervisor* (planning, multi-hive oversight) · ③ *New worker* (onboarding, unfamiliar) · ④ *Admin/founder* (platform-wide). Each stream ADDS its own specialized personas (attacker / disability / operator) below.

**Per-stream method (the same 6 beats every time):**
1. **Study-first** — mine the real denominator with a new `tools/<stream>_sweep.*` (measured baseline, NOT estimates).
2. **Spine** — draft/extend the stream's own `*_ROADMAP.md` with the sub-rows × lens matrix + floors.
3. **Build** the keystone fix first, then the rest cheapest-first.
4. **Live-persona-walk EACH phase** (the §0 doctrine) → record the screenshot/DB-proof.
5. **Ratchet** the measured-% board + a **forward-only gate** registered in `run_platform_checks.py`.
6. **Writeback** — skills (all relevant), memory, handoff.

---

## ① STREAM 1 — FORWARD-BUILD BACKLOG  *(the live-exercise frontier)*

**Proves:** everything we've BUILT is **exercised live end-to-end** — flipping the platform's remaining *attributed/render-strict* cells to **measured-live**. Tier-1 feature-debt is consumed ([[reference_canonical_gap_debt_2026_06_14]] / `CROSS_ARC_UFAI_REVIEW.md §3`); the gap now is *drive it*, not *build it*.
**Spine:** `CROSS_ARC_UFAI_REVIEW.md §3` (Tier-2/Tier-3 + try-before-accepting) is the existing backlog; this stream executes it.

| Phase | Unit | Live-persona-walk + MCP |
|---|---|---|
| **FB1 — Served-edge live round-trips** *(active frontier #6)* | Flip Arc E F-lens + Arc I I5/I7 cells attributed→live by invoking the **served** edge fns end-to-end (runtime already serves: edge + `py8000fwd` + `embed_server`). | Earnest personas (technician logs work → cmms-push; supervisor runs sync) drive the flows **through the UI** via Playwright MCP; postgres MCP confirms the row/cascade actually landed. |
| **FB2 — Browser-CI harness** ✅ BUILT *(#7 — biggest single live lever)* | Stand up the headless Playwright CI run that unblocks Arc D's ~811 strict-live cells + render cells. | **DONE 2026-07-01:** `tools/browser_ci_persona_walk.mjs` walks all 37 pages HEADLESS as the 4-persona roster (field-tech worker@mobile · supervisor@desktop · new-worker novice@desktop · admin supervisor@cross-hive-Lucena) running the authoritative `ufai_battery` referee per persona; emits `browser_ci_persona_board.json` + forward-only `browser_ci_persona_baseline.json`. Floor = the PERSONA-DELTA (console-error / dead-onclick / serious-WCAG / secret-leak) — NOT a re-derived Arc-D absolute. Gate `validate_browser_ci_persona.py` registered in `run_platform_checks` (group **Forward-Build**); real headless re-drive wired in `.github/workflows/browser-persona-ci.yml` (weekly + dispatch). **Found+fixed live:** (1) a battery secret-scanner false-positive (bare word `service_role` in a founder-console self-test label → tightened to credential-shape, improves every consumer); (2) the shared `.sc-tag` status-badge contrast class failing WCAG 4.5:1 (red 3.95 / grey 4.16) across ~13 pages → single-source lighten in components.css; (3) a fan-out of distinct per-page contrast / target-size / nested-interactive fixes. |
| **FB3 — k6 / load tier** *(#8)* | `tools/load_test.k6.js` already targets the local edge — "install k6," not "needs prod." | A *concurrent-burst* persona (many technicians at shift change) via k6 (or the curl/python burst substitute); Grafana MCP watches latency/error under load. |
| **FB4 — Live-LLM grounding/fabrication eval** *(Tier-3)* | Real grounding eval (Arc E 33 cells + Arc H fabrication) — single invokes are free-tier $0. | **Diverse asker personas**: earnest, edge-case, adversarial-prompt, and **Tagalog/multilingual** ([[feedback_eval_refusal_detection_multilingual]]); grade answers ⊆ DB truth set. |
| **FB5 — Try-before-accepting queue** | Probe each "attributed" cell live before accepting the ceiling: Arc F GBM fixture-eval · Arc H transcription recorded-sample · Arc I login brute-force (lower local GoTrue `[auth.rate_limit]`, observe lockout). | The relevant persona attempts the real action; classify by VERIFIED evidence ([[feedback_classify_by_evidence_not_heuristic]]), never by name. |

**Floor / exit:** every Tier-2/Tier-3 cell either flipped to **live** or re-classified covered-by-nature **with a built attempt on record** (no covered-by-nature without a real try — [[feedback_build_structure_to_make_it_liveable]]). **Fresh window opens at `build FB1`.**

---

## ② STREAM 2 — ARC R · SECURITY / ADVERSARIAL RED-TEAM  *(highest urgency — named open holes)*

**Proves:** the platform's **adversarial posture as ONE ratcheted, measured-% board** across all 4 attack surfaces (today the adversarial validators are scattered, each with its own baseline; no single number says "we are N% hardened"). **Has real open findings** flagged at scoping: an open **RAG IDOR**, live **P-lens ~66.7%**, and a board that **exit-0's on a regression** (false-green) — security debt with named holes shouldn't wait.
**Spine:** `SECURITY_ADVERSARIAL_ROADMAP.md` (Arc R, exists — extend, don't restart). Attack surfaces ≈ AuthZ/Access (IDOR/BOLA/BFLA/SSRF) · Input/Injection · AI/prompt · Tenant-isolation.

**Specialized personas (the attackers) — each walks LIVE:**
- **Cross-tenant intruder** — signed into Hive A, tries to read/mutate Hive B (every `?id=`, every edge fn, every realtime channel). Playwright MCP attempts the UI path; **postgres MCP confirms RLS denies at the DB**.
- **Malicious insider** — a `worker` trying to self-escalate to `supervisor` (replays the `hive_members` INSERT, role flips, approval queues). Extends Arc G's self-escalation closure.
- **IDOR/BOLA prober** — enumerates ids/keys across REST + edge fns; the open RAG IDOR is the keystone fix.
- **Brute-forcer / signup bot** — login rate-limit + signup anti-automation (folds Arc I I7/A live probe).
- **Injection / SSRF tester** — malformed payloads, SQL-LIKE escapes, SSRF on any fetch-by-URL edge fn.

**MCP toolkit:** Playwright MCP (UI attack walks) + postgres MCP (prove isolation holds at the data layer) + sentry MCP (did the attack surface an error/signal?).
**Keystone fixes (expected):** close the RAG IDOR · fix the board's exit-0-on-regression (real teeth) · unify the scattered validators into one `tools/security_adversarial_sweep.py` measured-% board.
**Floor / exit:** every attack-surface cell **verified-blocked by a live persona attempt** (not just a static check); P-lens floor met; one board, real teeth. **Fresh window opens at `build R0` (mine the denominator + unify the board).**

---

## ③ STREAM 3 — ARC U · ACCESSIBILITY / WCAG 2.2 AA  *(highest external value)*

**Proves:** **everyone** can operate the platform — keyboard-only, screen-reader, low-vision, color-blind, motor-impaired. This is **procurement reality** (enterprise/industrial + PH government buyers mandate WCAG) AND **field reality** (gloves, glare, one-handed, noisy floor).
**Spine:** *to draft* — `ACCESSIBILITY_UFAI_ROADMAP.md` (Arc U). Rows ≈ U1 keyboard operability · U2 screen-reader semantics (ARIA/roles/names) · U3 contrast & zoom (1.4.3/1.4.10/1.4.11) · U4 focus management & order · U5 target size & motor (2.5.8) · U6 non-color signalling (1.4.1) · U7 forms/errors (3.3) · U8 motion/timing.

**Specialized personas (the disabilities) — each walks LIVE:**
- **Keyboard-only user** — no mouse; Tab/Shift-Tab/Enter/Esc through *every* flow; nothing unreachable, no traps, visible focus. Playwright MCP keyboard-walk.
- **Screen-reader user** — every control has an accessible name/role; live-regions announce; headings nest. axe-core (CDN-inject, [[reference_grounded_battery_v2]]) + ARIA assertions.
- **Low-vision user** — 200% zoom + 400% reflow with no loss; contrast ≥ 4.5:1 (reuse the `aria_label_coverage` + contrast-token work from Arc V/W).
- **Color-blind user** — no status conveyed by color alone (risk badges, validation, charts).
- **Motor-impaired user** — target ≥ 24×24 (reuse Arc W's tap-target campaign), no fine-gesture-only path, generous timeouts.

**MCP toolkit:** Playwright MCP (keyboard + focus walks, axe-core inject) — primary. (mobile-maestro + designer skills for the fixes.)
**Floor / exit:** WCAG 2.2 AA across all 27 feature pages, each **proven by the relevant persona walk** + axe 0-violation ratchet; gate registered. **Fresh window opens at `build U0` (vendored axe + Playwright keyboard-walk → mine the violation denominator).**

---

## ④ STREAM 4 — ARC T · OBSERVABILITY / SLO  *(keeps every prior arc's fixes alive in prod)*

**Proves:** we can **SEE and ALERT on failure at runtime** — so the hundreds of build-time gates don't silently rot once real users hit the platform. Every prior arc proved *correct at build*; nothing watches *correct in production*.
**Spine:** *to draft* — `OBSERVABILITY_SLO_ROADMAP.md` (Arc T). Rows ≈ T1 golden-signal coverage (latency/traffic/errors/saturation) · T2 error capture (Sentry on every surface + edge fn) · T3 SLO definitions + burn-rate alerts · T4 alert routing (on-call, actionable, no noise) · T5 dashboards (per-tier health) · T6 log/trace correlation.

**Specialized personas (the operators) — each walks LIVE:**
- **On-call SRE** — when something breaks, does an **actionable** alert fire (right signal, right severity, links to the trace)? Not a noisy false-alarm.
- **Fault-injector** — deliberately breaks a flow (kill an edge fn, exhaust a quota, send a bad payload) and verifies it is **SEEN** in Sentry + surfaces on a Grafana dashboard within the SLO window. (Pairs the Arc-S resilience fault-injection harness.)
- **SLO reviewer** — confirms each tier's dashboard shows the right golden signals + burn-rate.

**MCP toolkit:** Grafana MCP (dashboards, alert rules, queries) + Sentry MCP (error capture, issues — note: GlitchTip write-only quirk, [[reference_glitchtip_sentry_mcp_compat]]) + Playwright MCP (trigger the fault via the real UI). Tooling already wired (Sentry + Grafana MCP).
**Floor / exit:** every tier has a golden-signal dashboard + at least one burn-rate alert **proven to fire by a live fault-injection walk**; gate asserts coverage. **Fresh window opens at `build T0` (inventory current Sentry/Grafana coverage → mine the gap).**

---

## §5 — SEQUENCING RATIONALE

1. **Forward-Build first** — cheapest + highest immediate truth-gain: it *exercises what already exists* (no new feature risk), and the **served-edge round-trips + browser-CI harness it stands up are reused by R, U, and T's persona walks**. Building the live-walk infrastructure first makes every later stream faster.
2. **R second** — the only stream with *named open holes* (RAG IDOR, 66.7% P-lens, false-green board). Real risk; do it once the live-attack harness from Stream 1 exists.
3. **U third** — highest *external/commercial* value (unlocks procurement); clean bounded sweep; reuses Stream-1's browser-CI + Arc V/W's contrast/tap-target work.
4. **T last** — best built once the above fixes exist, so observability watches a known-good baseline rather than alerting on churn.

**Cross-cutting (every stream):** stay LOCAL by default ([[feedback_stay_local_dont_suggest_prod_push]]); commit/deploy/external-keys/prod = Ian's standing gate, never a stop. Each stream ends with its own wrap + git-anchored handoff so the *next* stream opens clean.

---

## §6 — STATUS / NEXT

- **✅✅ Stream 1 (Forward-Build): COMPLETE (2026-07-01).** ✅ **FB1** (served-edge round-trips — cmms-webhook idempotency + 2 bugs) · ✅ **FB2** (browser-CI 4-persona headless harness + gate + CI + a11y/security fixes, 140/140 live) · ✅ **FB3** (load tier — `load_probe.py` 50-VU shift-change burst, p95 515ms/0% err, SLO met) · ✅ **FB4** (live-LLM grounding eval `tools/fb4_grounding_eval.py` + a VERIFIED 3-layer fabrication fix in `persona.ts` + `ai-orchestrator` coach deterministic guard, fabrication 6→1) · ✅ **FB5** (try-before-accepting fully evidence-classified: Arc I brute-force = GoTrue no-lockout ceiling · Arc F GBM = live `v_risk_truth` scores · Arc H transcription = env-ceiling needs audio fixture). All LOCAL/uncommitted.
- **✅✅ Stream 2 (Arc R — Security): COMPLETE (2026-07-01→03).** R0 (three named holes closed + gated: RAG IDOR · P-lens 66.7→100% · false-green board), R1 (DOM-XSS sink sweep clean), R2 (all 55 `verify_jwt=false` fns authZ-audited — 1 REAL find `pdf-ingest` anon-drainer fixed+gated; export-class cross-tenant VERIFIED secure), R3 (SRI pin-first 44→9, remainder = Ian-gated Tailwind Play-CDN migration). Board X100/Z100(17)/S100/P100. See `SECURITY_ADVERSARIAL_ROADMAP.md §5`. Arc R local queue DRAINED; only the Ian-gated Tailwind migration remains as forward backlog.
- **NEXT (Stream 3):** **Arc U (Accessibility / WCAG 2.2 AA)** — draft `ACCESSIBILITY_UFAI_ROADMAP.md`; FB2's serious-level persona-delta is already 140/140 clean, so Arc U's incremental denominator is the **FULL-impact WCAG 2.2 AA scan** (all levels + WCAG 2.2 SCs: target-size 2.5.8, focus-not-obscured 2.4.11, dragging 2.5.7) that FB2's serious-only floor does NOT capture — mine it with a full-impact axe pass across the 37 pages, then fix→gate. Then Stream 4 **Arc T (Observability)**.
- **⚠ Ian's deploy gate (standing, never a turn-stop):** the FB4 server-fn AI-behavior edits (`_shared/persona.ts` anti-invent rail + `ai-orchestrator` coach guard), the Arc R fixes (pdf-ingest authZ, hive.html link escHtml, 36 pinned+SRI CDN tags), and the Marketplace arc (companion grounding, `marketplace-listing-assist` fn) are all local/undeployed.
- **Pre-existing spines to reuse:** `CROSS_ARC_UFAI_REVIEW.md §3` (Stream 1), `SECURITY_ADVERSARIAL_ROADMAP.md` (Stream 2).
- **Spines to draft at window-open:** `ACCESSIBILITY_UFAI_ROADMAP.md` (U), `OBSERVABILITY_SLO_ROADMAP.md` (T). *(Note: FB2's `browser_ci_persona_walk.mjs` axe-per-persona harness IS the instrument Arc U will drive — the WCAG violations FB2 banks as its ratcheted backlog are Arc U's denominator.)*
