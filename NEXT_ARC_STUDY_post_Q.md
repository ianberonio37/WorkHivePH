# Next Arc — Comprehensive Study (post-Arc-Q, Round 3)

**Created 2026-06-23.** Method (unchanged from `NEXT_LAYER_STUDY.md` R1 → F/G and `NEXT_LAYER_STUDY_2.md` R2 → I):
enumerate the platform's dimensions → map what each prior arc covered → rank the un-swept ones by **risk × coverage-gap**
→ lay out each candidate as a scopeable spine → **Ian picks next context window.** ("Study, then roadmap, so we don't drift.")

> **Status: STUDY — all four candidates documented, awaiting Ian's pick.** Nothing built yet.

---

## §1 — What's already swept (11 arcs)

**Tiers (request/data path):** D Frontend · E Edge+DB · F Python API · G Data/DB · H AI/Companion · I Auth/Identity · J Realtime.
**Cross-cutting quality dimensions:** K Live-page journeys + UX critic · L Performance & Scale · **Q Domain Correctness (Live Value-at-the-Glass)** — just completed (11 real bugs found+fixed+gated; constant-table verification ~95%).

Every *layer* is swept and three *quality dimensions* are done. What remains are cross-cutting dimensions **no arc has swept end-to-end with the ratcheted, adversarially-verified, measured-% discipline.** The four below are ranked by risk × gap.

---

## §2 — Candidate A (★ recommended) · Arc R — Security / Adversarial Red-Team

**Thesis:** the **boundary-correctness twin of Arc Q.** Q proved the *value the user sees is right*; this proves the
*attack surface is right*. Every time the platform has been probed adversarially we found a real cross-tenant bug
(G DEFINER-IDOR, H view `security_invoker`, J realtime-RLS leak) — but those were all the **DB boundary**. The
**frontend (XSS/DOM/CSP), edge (SSRF/BOLA/BFLA), supply-chain (SRI/CVE/secret-egress), and AI (prompt-injection)**
attack surfaces have never been swept as one ratcheted frame. Highest risk for a multi-tenant industrial SaaS holding
client asset/maintenance data + a marketplace + an AI companion.

**Denominator (mine first):** ~36 frontend pages (client-JS sinks, `innerHTML`, `escHtml` coverage, CSP, SRI tags) ·
60+ edge fns (authZ per route, SSRF egress, input sanitation) · python API (input bounds, secret egress) · the
`_shared/*` AI chain (prompt-injection / jailbreak / data-exfil) · secrets/config inventory · dep manifest (CVEs).

**Lenses (OWASP Top 10 → 4):**
- **X — injection & XSS** (input→sink: stored/reflected/DOM XSS, SQLi via RPC args, command/template injection)
- **Z — authZ / access** (IDOR/BOLA/BFLA, CSRF, SSRF, missing-function-level-access, the 4 read-paths from Arc G/J)
- **S — secrets & supply-chain** (secret/key egress, SRI on every CDN script, dep CVEs, `verify_jwt`/config drift)
- **P — prompt & AI security** (prompt injection, jailbreak, system-prompt/PII exfil through the companion)

**Sub-layers:** R1 client-side (XSS/DOM/CSP/SRI) · R2 edge authZ (BOLA/BFLA/SSRF) · R3 secrets+supply-chain ·
R4 AI/prompt-injection · R5 marketplace trust/safety. **Floors:** X100/Z100/S95/P90 (security floors run high).
**Tooling:** `security` + `multitenant-engineer` skills, `tools/` adversarial probes, an attacker-persona Playwright/curl harness, `npm audit`/SRI checks; adversarial-verify each finding (refute-by-default) before claiming a vuln.

---

## §3 — Candidate B · Arc S — Resilience / Disaster-Recovery / Chaos

**Thesis:** the system must **survive failure.** For a maintenance product (logbook, asset register, sensor data),
**data loss = trust loss.** Arc L touched burst-resilience and Arc H touched provider-fallback, but no arc has swept
*what happens when a dependency dies*, *can we restore*, or *do we corrupt on partial failure*.

**Denominator:** each external dependency (Supabase DB/Auth/Storage/Realtime, Groq/AI providers, the python API,
Resend, any CDN) × its failure mode · backup/restore coverage per table · idempotency of every write path ·
offline/degraded-mode coverage per page.

**Lenses:**
- **F — failure-tolerance** (each dependency-down → graceful, not a white screen)
- **R — recovery** (backup/restore proven; measured RPO/RTO; no silent data-loss window)
- **C — consistency** (idempotent writes, no partial-write corruption, exactly-once on retries)
- **D — degradation** (offline/read-only mode, queue-and-retry, the PWA service-worker fallback)

**Sub-layers:** S1 dependency-down behavior · S2 backup/restore · S3 idempotency/partial-failure · S4 offline/degraded ·
S5 data-integrity-under-failure. **Floors:** F90/R95/C100/D85. **Tooling:** chaos probes (stop containers — we already
`docker stop/start` routinely), restore drills, the existing `validate_idempotency` extended, k6 burst (Arc L).

---

## §4 — Candidate C · Arc T — Observability / Monitoring / SLO

**Thesis:** the **meta-layer** that keeps every other arc's fixes alive in prod — *can we see and alert on failure?*
Audit logs exist, but there's no structured-logging / error-tracking / SLO / alerting maturity sweep. **Sentry and
Grafana are already wired as MCP servers**, so this arc can drive real dashboards/alerts, not mock them.

**Denominator:** every edge fn + page × (structured log? error captured? metric emitted? traced?) · the alerting
rules · the SLO definitions · audit-trail completeness.

**Lenses:**
- **V — visibility** (structured logs, traces, metrics coverage across fns/pages)
- **D — detection** (error tracking via Sentry, anomaly on key metrics)
- **A — alerting** (SLO-based, actionable, low-noise, routed)
- **R — response** (runbooks, on-call schedule, measured MTTR)

**Sub-layers:** T1 structured logging · T2 error tracking (Sentry) · T3 metrics/dashboards (Grafana) · T4 SLO+alerting ·
T5 audit/trace completeness. **Floors:** V90/D90/A85/R80. **Tooling:** `mcp__sentry__*`, `mcp__grafana__*`, the existing
audit-log + `validate_observability`.

---

## §5 — Candidate D · Arc U — Accessibility (WCAG 2.2 AA, deep)

**Thesis:** every user can **operate** it. Arc K cleared `:focus-visible` platform-wide and left a per-page
tap-target/contrast backlog, but no deep WCAG sweep (screen-reader, keyboard, ARIA semantics, reduced-motion,
forms/errors) exists. Real for Philippine field workers (gloves, sunlight, varied/low-end devices) **and** for
enterprise/government procurement, which often *gates* on an a11y conformance statement.

**Denominator:** all ~36 pages × every interactive element × the WCAG 2.2 AA success criteria · forms + error states ·
dynamic/live regions · the companion/voice UI.

**Lenses (WCAG POUR):**
- **P — perceivable** (contrast ≥ AA, alt-text, captions, color-independence, text-resize)
- **O — operable** (full keyboard, no-trap, target-size ≥ 24px, timing/no-flash, skip-links)
- **U — understandable** (labels, error identification+suggestion, consistent nav, language)
- **R — robust** (valid ARIA name/role/value, live-region semantics, AT compatibility)

**Sub-layers:** U1 perceivable · U2 operable · U3 understandable · U4 robust/AT. **Floors:** P95/O90/U90/R90.
**Tooling:** `axe-core` (already vendored at `tools/vendor/axe.min.js`), Playwright keyboard-walk, a screen-reader
semantics probe, `qa-tester` + `mobile-maestro` + `designer` skills.

---

## §6 — The pick (Ian, next context window)

| Arc | Proves | Risk × gap | One-liner |
|---|---|---|---|
| **R · Security** ★ | the attack surface is right | **highest** | the boundary-twin of Q; adversarial probing always finds real bugs |
| **S · Resilience/DR** | the system survives failure | high | data loss = trust loss; never swept |
| **T · Observability/SLO** | we can see + alert on failure | high (meta) | Sentry + Grafana MCP ready to drive |
| **U · Accessibility** | everyone can operate it | medium-high | procurement + field-worker reality; K only scratched it |

**Recommendation: Arc R — Security / Adversarial.** Highest risk, genuinely un-swept frontend/edge/supply-chain/AI
surface, completes the Arc-Q correctness thesis (value-right + boundary-right), and the platform has a 3-for-3 record
of yielding real cross-tenant vulns the moment it's probed. **But it's Ian's pick** — all four are scoped and ready.
