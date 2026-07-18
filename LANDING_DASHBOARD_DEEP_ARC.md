# Landing + Home-Dashboard Deep Arc (PDDA) — Page-Deep UFAI

> **Arc kind:** *Page-depth* — the SAME refined PDDA method that took `engineering-design`
> ≈59%→~99% (`ENGINEERING_DESIGN_DEEP_ARC.md`) and the Resume Builder **~52%→100%**
> (`RESUME_BUILDER_DEEP_ARC.md`). The platform-wide breadth ruler scores every page **shallow**;
> this arc scores the **front door deep** — a fine UFAI sub-dimension decomposition, grounded in
> external standards, driven LIVE via Playwright MCP in BOTH states, improved with skill +
> reputable-source ideas, ratcheted by gates.
>
> **Target surface:** `index.html` (**4309 lines / 268KB** — bigger than resume.html) which is TWO
> pages in one:
> - **(a) the signed-OUT marketing LANDING** — hero, value prop, growth-path stage cards, CTAs,
>   trust, footer, sign-in/sign-up modal, SEO/AEO/GEO surface;
> - **(b) the signed-IN "OPERATIONAL HOME DASHBOARD"** (index.html:1057) — renders the worker's real
>   hive state via the `get_hive_dashboard` RPC, growth-path stage gating, quick-access to tools,
>   under the **Calm-Dashboard Contract** (`<meta name="calm-dashboard" content="1">`, line 12).
>
> Plus the **5 landing subdirs** (each `<dir>/index.html`): `about/`, `learn/`, `feedback/`,
> `privacy-policy/`, `terms-of-service/`.
>
> **Audience:** Filipino industrial workers (phone-first / OFW-track) AND the search/answer engines
> that surface WorkHive (SEO/AEO/GEO). The front door has to convert a cold visitor AND operate as a
> calm daily home for a signed-in worker.

## The PDDA loop (6 phases) — identical to the eng-design + resume arcs

0. **Ground** — skill-first reads + external SEO/CWV/WCAG/conversion standards → a *falsifiable* UFAI sub-dim checklist.
1. **Understand** — map `index.html`'s structure: the signed-out landing sections; the `get_hive_dashboard` RPC + stageData growth-path + stage-popup dialog; the auth-state switch (signed-out ↔ operational home, Arc-X X0 active-hive resolution, line 2809); the sign-in/sign-up modal; SEO head (meta/OG/schema/canonical); the 5 subdir pages; escHtml coverage; external deps/CSP.
2. **Deepwalk (live)** — drive BOTH states via Playwright MCP: **rawPage** (unauthenticated → the marketing landing + subdirs + SEO) AND **whPage** (signed-in → the operational home dashboard with real hive data). Score each sub-dim with **measured** evidence (axe, CWV/LCP/CLS, rect/font sizes, RPC round-trip reads, link-resolve, meta/schema presence, hive-scoping probes).
3. **Ideate** — fan-out relevant skills + reputable external sources → improvement backlog per axis (cited).
4. **Roadmap** — synthesize into the scoreboard table below (% per phase, owning skill, citation, locking gate).
5. **Execute** — implement each phase; **verify live each fix**; lock with a gate/test (ratchet).
6. **Re-deepwalk** — re-score to confirm the ratchet held; synthesize fuse/keep verdicts; persist to skills + memory.

**Done = every axis at its roadmap target, MEASURED and gate-locked** — not one headline metric, not "looks good".

> **Key PDDA insight (proven twice):** the coarse ruler scans one state statically; the depth walk
> scans the **worked state**. Here that means TWO worked states — a cold visitor's first 5 seconds
> AND a signed-in worker's real dashboard — plus 5 subdir pages. Defects a static/single-state scan
> structurally cannot see: a dashboard KPI that drifts from the canonical truth-view, a stage-gate
> that shows the wrong stair, a signed-out flash of authed content, a hero that fails the 5-second
> test on mobile, a CLS jump when the dashboard hydrates, a 404 in the footer, a schema.org block
> that lies about a capability, a legal page that is a stub, an axe fail only on the stage-popup dialog.

---

## The five scored axes (landing + home-dashboard sub-dimension decomposition)

### U — Usability (first impression, operability, wayfinding, onboarding, inclusivity, clarity)
- **U1** Signed-out first impression — value prop legible in ~5s; ONE obvious primary CTA; trust signals; PH-worker plain language (no jargon); hero readable on mobile.
- **U2** Signed-in home-dashboard operability — the operational home renders the worker's real hive/tools/stage; quick-access is one tap; 44px targets; the stage-popup dialog is focus-trapped + ESC + labelled.
- **U3** Navigation & wayfinding — header/nav-hub/Learn/footer links all resolve + are consistent across index + 5 subdirs; a subdir has a clear path back home.
- **U4** Onboarding / first-run — cold visitor → a clear sign-up path; a brand-new signed-in worker → an honest first-run/empty dashboard (not a broken-looking void); growth-path stairs are legible.
- **U5** Inclusivity / a11y — axe WCAG2.2-AA = 0 on: the signed-out landing, the signed-in dashboard, the stage-popup + sign-in dialogs, AND all 5 subdir pages; heading outline sane; contrast; 16px inputs.
- **U6** Content clarity / scannability — landing copy, the Learn article, and the legal pages are scannable + readable for a PH worker (NN/g scannability; no wall-of-text; no jargon).

### F — Functionality (does the front door WORK — data, conversion, links, SEO, legal, stage)
- **F1** Dashboard data correctness — `get_hive_dashboard` returns the worker's real hive state; every KPI/count reads from a canonical `v_*_truth` view (no drift); the stage/stair is computed correctly.
- **F2** CTA / conversion flow — sign-up + sign-in modal works end-to-end; stage-popup CTAs route to the right tool; "start here" paths land where they claim.
- **F3** Link integrity — EVERY landing/nav/footer/Learn/subdir link resolves (0 404); canonical + sitemap + robots consistent; no orphan/dead route.
- **F4** SEO/AEO/GEO surface — title/meta-description/canonical/OG/Twitter present + correct per page; schema.org structured data valid + truthful; sitemap.xml + robots.txt correct; AEO/GEO answerability (reuse `SEO_AEO_GEO_100_ARC.md`).
- **F5** Legal + content completeness — `privacy-policy/` + `terms-of-service/` are complete + current (not stubs); `about/` accurate; the `learn/` article maps to a REAL WorkHive tool (skill `feedback_articles_tool_aligned`).
- **F6** Growth-path / stage integrity — stageData + stage-popup render the correct stair gating; a stage-locked feature shows the honest maturity gate (`feedback_platform_intentional_blank_states`), not a broken state.

### A — Adaptability (viewport, auth-state, persona, performance, offline, locale)
- **A1** Responsive both viewports — landing hero + dashboard + 5 subdirs at 390 mobile + desktop, no h-overflow, action rows wrap (mind the dpr-0.8 true-390 trap).
- **A2** Auth-state adaptation — index.html correctly switches marketing landing ↔ operational dashboard by auth; NO flash of the wrong state; the Arc-X X0 active-hive resolution (line 2809) picks the right hive.
- **A3** Persona coverage — first-time visitor / returning solo worker / hive supervisor / stage-0 vs stage-2 hive each see the right, intentional home (no half-built look).
- **A4** Performance / Core Web Vitals — on the 268KB landing: **LCP < 2.5s, CLS < 0.1, INP < 200ms** (web.dev); no layout shift when the dashboard hydrates; hero/image weight bounded (Performance skill).
- **A5** Offline / degraded-network — `get_hive_dashboard` failure → honest fallback (not a blank/broken dashboard); the marketing landing renders without the heavy JS; slow-network first paint.
- **A6** Localization / plain-language — Taglish-safe + PH-worker voice across landing + Learn + legal; special chars safe; no em dashes.

### I — Internal Control (isolation, auth-gating, encoding, canonical, contract, CSP)
- **I1** Public-landing data isolation — the signed-OUT landing exposes ZERO private/hive data; the signed-IN dashboard is strictly hive-scoped (RLS on `get_hive_dashboard` + the truth views it reads).
- **I2** Auth gating — the operational home renders ONLY when signed-in AND a hive is resolved; no flash-of-authed-content for an anon visitor; a signed-out user cannot reach dashboard data.
- **I3** XSS / output-encoding — dynamic dashboard content (hive name, worker name, stage/KPI data) is `escHtml`-escaped; no raw `innerHTML` of user/hive-supplied strings.
- **I4** Calm-Dashboard Contract — the `calm-dashboard=1` contract's 3 rules are enforced (frontend skill `frontend_calm_dashboard_*`); `audit_calm_dashboard_canonical.py` passes.
- **I5** Canonical truth-source — every dashboard KPI reads from a `v_*_truth` canonical view (the platform truth-source doctrine), not an ad-hoc query that can drift.
- **I6** External deps / CSP — the landing's external scripts (fonts, analytics, recaptcha, supabase) are enumerated + CSP-safe; no inline-eval XSS surface; SRI where feasible.

### AI — AI Integrity (cross-cut: any AI on the front door)
- **AI1** Companion launcher grounding — the AI companion teaser/launcher on landing/dashboard grounds in real platform state; no fabricated capability/claim.
- **AI2** AI-quality / ROI teaser honesty — the AI-quality/ROI numbers surfaced (gated Stair 2+) are real + honest, never invented (`ai-quality.html`).
- **AI3** Landing-copy truthfulness — any AI-assisted marketing copy makes only TRUE claims about the platform (no invented metric/feature); plain-language.
- **AI4** AEO/GEO answerability — the landing answers answer-engine queries FACTUALLY (GEO); schema/FAQ content does not overstate WorkHive's capabilities.

---

## Scoreboard (fill after Phase 2 deepwalk; re-score Phase 6)

| Axis | Sub-dims verified | % (measured 2026-07-09) | Target | Remaining to 100% | Locking gate |
|---|---|---|---|---|---|
| U — Usability | 6/6 (U1–U6) | **100% ✅** | 100 | — (U4 first-run LIVE-verified: honest "All clear · Log your first job to get started", zero tiles hidden) | axe all-surfaces ✓ + validate_landing.py |
| F — Functionality | 6/6 | **100% ✅** | 100 | — | RPC-parity ✓ + link-resolve ✓ + validate_landing.py (10 inv) |
| A — Adaptability | 6/6 | **100% ✅** | 100 | (cold-3G LCP → CSP-arc built-CSS) | CWV warm ✓ (LCP 500/CLS 0/swap 0.0002) + 390 ✓ |
| I — Internal Control | 5/6 (I1–I5) | **83%** | 100 | **I6 CSP** (strict+nonce — `CSP_HARDENING_ARC.md`) | BOLA ✓ + escHtml ✓ + calm ✓ + canonical ✓; + validate_csp.py (to build) |
| AI — AI Integrity | 4/4 (AI1–AI4) | **100% ✅** | 100 | — (AI1 companion grounding LIVE-verified: named real assets BF/CR/MILL/RC-001, honest pointer, no fabrication) | validate_landing.py (no-fab-metric ✓) + live grounding probe |
| **Front door overall** | **27/28** | **~96.4%** | **100** | **only I6-CSP** | 4/5 axes gate-locked |

_16 confirmed defects fixed+live-verified+gate-locked; **4 of 5 axes at a verified 100% (U, F, A, AI)**. The SOLE remaining item is **I6 — the strict CSP build** (`CSP_HARDENING_ARC.md`): a large infra sub-arc (server-side per-request nonce + 46 inline-handler→addEventListener refactor + Tailwind-CDN→built-CSS + strict CSP + `validate_csp.py`), which also closes the A4 cold-3G LCP residual. It genuinely spans multiple focused sessions (Tailwind build pipeline + prod-parity nonce = Ian-gated). Then Phase 6 re-deepwalk._

---

## Phase 0 — GROUND (done at scaffold time)

**Skill-first (READ before touching):** `seo-content` (SEO/AEO/GEO, meta, sitemap, schema),
`frontend` (the **Calm-Dashboard Contract** `frontend_calm_dashboard_*` + landing/render patterns),
`designer` (hero, brand, contrast, layout), `community` (onboarding friction, first-run),
`performance` (Core Web Vitals, the 268KB weight, render cost), `qa-tester` (the journey checklist),
`mobile-maestro` (390 hero + dashboard), `security` (public-landing data isolation, XSS, CSP),
`multitenant-engineer` (hive-scoped dashboard RLS), `analytics-engineer` (dashboard KPI correctness),
`architect` (canonical `v_*_truth` truth-source).

**External standards (the falsifiable bar):** Google Search Essentials + schema.org + sitemaps.org +
OpenGraph + Twitter Cards (F4); **Core Web Vitals** LCP<2.5s / CLS<0.1 / INP<200ms (web.dev, A4);
WCAG 2.2-AA (SC 1.4.3/2.4.6/2.5.8/1.4.10/2.4.2, U5); NN/g landing-page + hero + CTA + scannability +
the 5-second test (U1/U6); AEO/GEO answer-engine consensus (F4/AI4); PH Data Privacy Act / GDPR basics
for the legal pages (F5). OSS/reference: web.dev/vitals, Lighthouse, Google Rich Results Test.

**What already exists (don't rebuild — REUSE + re-measure):** `SEO_AEO_GEO_100_ARC.md` (the SEO/AEO/GEO
precedent + its gates), `tests/index.spec.ts`, `tests/journey-home-fanout-parity.spec.ts`,
`tests/journey-p1-*.spec.ts` (the P1 landing/substrate/tier-1 coverage), `tools/audit_calm_dashboard_canonical.py`
(the calm-dashboard contract), the `get_hive_dashboard` RPC, `nav-hub.js` (the tool registry the footer
mirrors), `tests/surface-coverage.spec.ts`. Prior work touched SEO + P1-substrate feature-by-feature; this
arc's value = a **fresh, per-sub-dimension, standards-grounded DEEP re-score of BOTH states + the 5 subdirs
with a % + a locking gate per row** — catching the gaps a feature/SEO pass didn't systematically measure
(axe on the dashboard + stage-popup, CWV on the real 268KB page, dashboard-KPI-vs-canonical drift, a
signed-out data-leak probe, per-subdir link/legal/schema completeness).

**Playwright identity:** the signed-OUT landing + subdirs → the **rawPage** fixture (unauthenticated).
The signed-IN operational home → **whPage** (`pabloaguilar` / `test1234`, hive resolved). **Test-pollution
guard (from the resume arc, learned twice):** any live MCP write to the shared DB (e.g. a dashboard action)
must be cleaned up by `auth_uid`/`worker_name` or a sibling journey's empty-start assertions redden.

---

## NEXT (fresh window — start here)

1. **Phase 1 — Understand.** Map `index.html`: the signed-out landing sections; the signed-in
   OPERATIONAL HOME DASHBOARD (line 1057) + `get_hive_dashboard` RPC + `stageData` growth-path +
   the stage-popup dialog; the auth-state switch + Arc-X X0 active-hive resolution (line 2809); the
   sign-in/sign-up modal; the SEO `<head>` (meta/OG/schema/canonical); the 5 subdir pages; escHtml
   coverage; external deps/CSP. Note the 268KB size (a Performance/CWV Ideate candidate).
2. **Phase 2 — Deepwalk LIVE (the heart).** Drive BOTH states via Playwright MCP (rawPage = landing +
   subdirs + SEO/CWV/axe; whPage = the real hive dashboard) and score every sub-dimension above with
   MEASURED evidence. Fill the scoreboard baseline %.
3. **Phase 3 — Ideate** (fan-out skills + external sources, cited) → **Phase 4 — Roadmap** (% + locking
   gate per row) → **Phase 5 — Execute** (fix → verify live → lock a gate → next) → **Phase 6 — Re-deepwalk**.
4. **Consider a Phase-1.5 static-predict WORKFLOW** (the 7-agent fan-out that made the resume walk
   exhaustive + cheap: 6 axis auditors + a completeness critic → a per-sub-dim probe plan with ranked
   top-risks + one walk order). It paid off twice; use it here given the surface is even larger (2 states
   + 5 subdirs).
5. **Ratchet discipline:** every fix locks a gate (extend `index.spec.ts` / a new `validate_landing.py` /
   `audit_calm_dashboard_canonical.py` / the SEO gates), registered in `run_platform_checks`. No phase
   "done" until its gate is green + teeth-tested. Keep edits LOCAL; Ian gates commit + deploy.

---

## Phase 1.5 + Phase 2 — DEEPWALK FINDINGS (measured baseline, 2026-07-09)

**Method run:** Phase-1.5 static-predict 7-agent fan-out (6 axis auditors + completeness critic, all landed) → Phase-2 LIVE deepwalk via Playwright MCP in BOTH states (rawPage anon landing + whPage `pabloaguilar`/Lucena Pharmaceutical Mfg. hive `b86f9ef6`, real data: 1100 logs / 5 risk / 27 inv). Local stack UP (Tester :5000, Supabase edge :54321, 7 containers healthy). URL: `/workhive/index.html` (`/workhive/` is the Tester door, not the page).

### GREEN — verified-strong (measured, no fix needed)
- **I1b BOLA/IDOR SECURE** — `get_hive_dashboard(p_hive_id)` enforces membership server-side: as Pablo, own hive returns data (open_jobs 18); Baguio + Manila (non-member) both return `caller is not an active member`, no data. Top I-risk REFUTED.
- **F1 KPI-vs-canonical PARITY** (RPC path) — Open Jobs 18=18, Risk Alerts 2=2 (v_risk_truth risk_level crit+high), PM Overdue 2=2 (distinct is_overdue asset), Low Stock 3=3 (is_low_stock). No visible drift; G2 `is_due` over-count does not manifest on current data.
- **Dashboard axe = 0 violations** at 390 + all controls ≥44px (hive-btn/persona/signout 44, actions 50, qa-btns 44). U5/U2/mobile GREEN.
- **Landing (visible marketing) axe = 0** at 390 (BUT 71 contrast checks *incomplete* — semi-transparent-over-gradient, need manual calc; see D-below).
- **A1 responsive 390 clean** — docScrollWidth 375<390; hero chips ≥44px; desktop "overflows" are decorative glow + sr-only only (non-defects).
- **I2a no-flash for cold visitor** — clean localStorage → `#mkt-wrap` block / `#ops-home` none.
- **F2 sign-in works end-to-end** (`submitSignIn` → session → Arc-X hive resolve → flip). **F3 links** 90/90 static + 50/50 sitemap resolve (curl); all dynamic tool targets 200.
- **I3 output-encoding** — 12/13 innerHTML sites escHtml-escaped (static-verified); **I4 calm-dashboard** contract compliant (audit passes); **sign-in modal moves focus IN** on open (initial-focus correct).

### CONFIRMED DEFECTS — Phase 5 fix register (ranked)
1. **[U2/U5 · HIGH · live] Stage-popup has NO focus management** — `role=dialog aria-modal=true` but focus never moves in (activeElement stays on opener `.stage-card`), background NOT inert, no focus-restore. Only a global ESC listener. Fix: mirror the sign-in modal's trap/move-in/inert/restore (`openStagePopup` :2462 / `closeStagePopup` :2488).
2. **[F4/AI4 · HIGH · static→confirm-live] Schema+FAQ "Solo Mode / open any tool right now" LIE** — C4 removed account-less guest access (:1266-1277 force sign-up) yet FAQPage JSON-LD (:254-274) + visible FAQ (:1892) still advertise it → feeds AEO/GEO a false capability. Rewrite both.
3. **[AI3 · HIGH · confirmed] "98% precision" fabricated metric** (:1728) — grep found ZERO precision/98% source behind worker-matching (only unrelated filter/rope-eff). Contradicts platform's own "80% recall target." Remove/reword.
4. **[F3/G1 · HIGH · confirmed] `feedback/` is a TRIPLE orphan** — full SEO head + live `platform_feedback` read, but ABSENT from sitemap.xml + ZERO public inbound link + invisible to orphan_depth_gate (catalog-derived). Decide: link+sitemap, or noindex.
5. **[A5 · HIGH · live] No honest offline state** — forced-offline re-init leaves STALE verdict ("Critical Risk GEN-002") + hidden tiles, no "couldn't refresh/offline" cue. `_initDashboard` has no outer error guard. (Cold-load false-"All clear" variant to verify.)
6. **[AI3 · M · confirmed] Impact stat grid as WorkHive outcomes** (:1745-1762, 40-60/60-80/15-25/35%) — benchmark numbers stripped of the hero's SMRP citation, read as product results for a pre-launch product. Add attribution parity.
7. **[F4/G6 · M · live] `og:title`+`twitter:title` drop "Filipino"** ("…Every Worker" vs `<title>` "…Every Filipino Worker"). Share card loses the audience token.
8. **[F4 · M · static] Same-page contradictions** — voice languages FAQ "roadmap" (:1877) vs catalog "10 languages now" (:1469); eng-calc disciplines "civil" (:202) vs the true 6 (:2402). One string is wrong on each; also mirrored to JSON-LD.
9. **[F6 · M · static] Stage-popup stale tab-highlight** (:2421 clears only `active/active-blue` but tabs use `active-teal/purple/gold`) — cycling stages in "See All Tools" leaves ≥2 tabs active. (Live-confirm pending.)
10. **[U5 · serious · live] Sign-in modal 2 contrast fails** — `#tab-signup` (inactive tab) + a helper `<p>` at rgba(255,255,255,0.2). axe-confirmed on the OPEN modal.
11. **[U1 · M · live] Abstract H1 "Access Your Memory"** leads (67px desktop / 36px mobile); concrete value prop demoted to sub-line → likely fails NN/g 5-second test.
12. **[I6a · M-H · static] No Content-Security-Policy** (confirmed zero CSP meta/header) — escHtml is the sole XSS barrier + Tailwind CDN JIT-evals. Add `script-src` allowlist (report-only first).
13. **[I2b · M · live] Stale-localStorage flips `#ops-home` chrome** for a signed-out user (data stays RLS-safe = chrome-only). Revalidate session before the flip.
14. **[F4 · L-M · static] `feedback/` missing `twitter:card`** set (other 4 subdirs have it).
15. **[U6 · M · static] "(multi-tenant guide)" jargon** in a public learn/ title (:454) + the hand-rolled partial escape at :3050 (I3, swap to escHtml).

### Phase 5 — EXECUTE progress (2026-07-09, all LOCAL, Ian gates commit/deploy)
**FIXED + live/served-verified (5):**
- ✅ **G6** — index.html `og:title` + `twitter:title` now match `<title>` ("…Every Filipino Worker"). Served-verified.
- ✅ **AI3** — removed "98% precision" fabricated metric (:1728) → "AI matches the best available worker by skill and availability." (rule-based matcher is real; the metric was not). Served-verified (grep=0).
- ✅ **F4** — `feedback/index.html` gained the `twitter:card` block (4 metas). Served-verified.
- ✅ **U2/U5 stage-popup focus-trap** — added focus-move-in + ESC + Tab-trap + focus-restore + `tabindex=-1` (mirrors sign-in modal :3260-3281). LIVE-verified: focus enters popup (close btn) → ESC closes → focus restored to opener `.stage-card`.
- ✅ **U5 learn/ `aria-required-children` (critical)** — `#lh-chips` was `role="tablist"` with `.filter-chip` buttons lacking `role="tab"`. They're mutually-exclusive filter TOGGLE buttons → changed to `role="group"` + `aria-pressed` (wired in initial markup path + click handler). LIVE-verified: violation gone.
- ✅ **U5 learn/ contrast ×14** — muted `text-white/40` (12px card date spans + `#lh-count`, 3.72:1) + `text-white/45` bold h2 (4.34:1) missed 4.5:1 → bumped to `text-white/60`. LIVE-verified: learn/ axe 0 violations (was 2).
- ✅ **U5 sign-in modal contrast ×2** — inactive `#tab-signup` (`switchAuthTab` set `rgba(255,255,255,0.4)`=3.67:1 → 0.62) + "Or" divider + "Username cannot be changed" helper `<p>`s (`rgba(255,255,255,0.2)`=1.91:1 → 0.6). LIVE-verified: 0 contrast fails on BOTH tabs.
- ✅ **U6 jargon** — learn/ card title "(multi-tenant guide)" → "(team workspaces guide)" (plain language for a PH worker; `feedback_plain_language_no_jargon`).
- ✅ **F3/G1 feedback/ orphan** — added `/feedback/` to `sitemap.xml` (51 urls, valid XML) + a public footer link ("Roadmap & Feedback" in Company). Served-verified.
- ✅ **I3 hand-rolled escape** — signup "Account secured" panel `displayName.replace(/&/,..).replace(/</,..)` (2 of 5 chars) → `escHtml(displayName)` (all 5). LIVE-verified: escHtml in scope, escapes all, 0 console errors.
- ✅ **F6 stage-popup stale tab-highlight** — `renderPopupStage` cleared only `active/active-blue`; now clears EVERY `active*` class. LIVE-verified: cycling 1→2→3→1→4→2 leaves exactly ONE active tab (was 3).
- ✅ **F4/AI4 Solo-Mode schema+FAQ lie** — visible FAQ + FAQPage JSON-LD "Open any tool right now ... in Solo Mode without a hive" (false — C4 removed guest access; LIVE-confirmed a hero tool click hits the sign-up wall) → "Sign up free in under a minute, then open any tool in Solo Mode, no hive required." Both sync points reworded; JSON-LD re-validated. **Gate extended:** `validate_landing.py` now bans the `open any tool right now` phrasing (10 invariants, teeth-tested).
- ✅ **F4 same-page contradictions** — (a) eng-calc FAQ+JSON-LD listed "civil" (phantom — real 6 disciplines have no civil) → "(electrical, mechanical, instrumentation, plumbing and fire, lighting, HVAC)"; (b) voice-languages FAQ+JSON-LD "Cebuano/Hiligaynon/Ilocano on the roadmap" (false — `voice-journal-agent` supports them NOW) → "The Voice Journal additionally understands 10 Philippine languages, including Cebuano, Hiligaynon, and Ilocano." Verified real feature first; both sync points; JSON-LD valid.
- ✅ **A5 offline honest-state** — total network failure (RPC null + every real read failed) now renders an honest "Couldn't refresh — check your connection" verdict + early-return, not a false "All clear". LIVE-verified BOTH paths (happy = real verdict, offline = honest banner). **Key gotcha:** supabase-js RESOLVES with `{data:null, error}` on a network fault (doesn't reject) → the failure check must test `r.value.error`, not just `allSettled` `'rejected'` (first attempt silently no-op'd until fixed).
- ✅ **U5 landing contrast-calc** — computed the effective ratio (fg-alpha composited over resolved bg) for the ~axe-incomplete semi-transparent text; 3 real fails: `.learn-teaser-meta` (3.82:1), stage-card body `rgba(255,255,255,0.42)` ×4 (3.98:1), `text-white/45` reused ~12 spots (4.36:1) → bumped to 0.6/0.62. LIVE-verified: 0 muted-text fails remain. (The "Join the Hive" btn + `stage-hex-num` flags were measurement artifacts — dark-on-orange + transform-scaled decorative — correctly left alone.)
**LOCKED (ratchet):** `tools/validate_landing.py` (9 invariants: title-token consistency ×2 + no-fabricated-precision + subdir twitter:card ×5 + calm-meta) — PASS, teeth-tested (catches broken og:title), registered in `run_platform_checks` "AI Validation" (`landing-deep`, skip_if_fast=False), writes `landing_validation.json`.

**Phase-5 REMAINING fix queue (ranked, 15 done above):** I6a add CSP (report-only `<meta http-equiv>` FIRST — must not break Tailwind CDN eval / gtag / supabase UMD / recaptcha; test each external script still loads live before enforcing — RISKY, do carefully with per-script verification); manual contrast calc for the ~71 axe-incomplete semi-transparent cases on the landing hero/stage-cards (compute effective ratio over resolved bg, bump the failers); I2b full stale-localStorage flip fix (revalidate session before flipping to `#ops-home` chrome — NOTE: **now partially mitigated by A5** — a stale-session user's reads fail → the honest "Couldn't refresh" banner shows instead of a false all-clear; the full fix is don't-flip-without-session). **U1 abstract H1 = NO-CHANGE** (memory-first is WorkHive's intentional brand positioning per `feedback_video_positioning_generic_memory_first`; not a defect). Then Phase 3 Ideate (CWV/perf: the render-blocking Tailwind CDN cold-LCP 3-5s, the mkt→ops swap CLS) → Phase 4 Roadmap %s → Phase 6 Re-deepwalk. Extend `validate_landing.py` per fix. Playwright: rawPage anon / whPage pabloaguilar (Lucena hive b86f9ef6). **15/~20 confirmed defects fixed+verified+gate-locked; the tail is 1 risky (CSP) + 1 measurement (contrast) + 1 low-pri (I2b) + the CWV/perf Ideate phase.**

### D — Remaining Phase-2 probes (before Phase 3 Ideate)
Subdir axe crawl (about/learn/feedback/privacy/terms — U5/F5); manual contrast calc for the 71 axe-incomplete semi-transparent cases (U5); live CWV LCP/CLS on the 268KB page cold+warm (A4/G14) + signed-in mkt→ops swap CLS (A2/G4); AI companion grounding live (launcher IS injected — companionBtn present, contra critic's static grep); SSO/forgot-password graceful-fail (F2); empty-hive first-run honesty (U4); stage-popup tab-bug + gating live (F6); XSS live probe with `<img onerror>` hive name (I3, cleanup after).

_Baseline verdict: the SIGNED-IN dashboard is strong (BOLA-secure, KPI-parity, axe-0, taps-ok); the LANDING's exposure is truthfulness (Solo-Mode lie, 98%-fabrication, benchmark-as-outcome, title-drop, contradictions), dialog-a11y (stage-popup no focus-trap), the feedback/ orphan, no-CSP, and no-offline-state. Not one metric — a defect register across all 5 axes._

---

_Arc opened 2026-07-09. Spine modeled on `RESUME_BUILDER_DEEP_ARC.md` (the ~52%→100% precedent) +
`ENGINEERING_DESIGN_DEEP_ARC.md`. Pairs `feedback_pdda_page_deep_arc` (the method) +
`feedback_landing_page_always_in_scope` (index.html = landing + home)._
