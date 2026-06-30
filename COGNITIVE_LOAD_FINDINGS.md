# Cognitive-Load Walk — Findings Log

**Owner:** Ian + Claude · **Started:** 2026-06-25 · **Method:** Ian-guided live walk (Playwright MCP, signed in as a real seeded user) — Ian surfaces one issue at a time; Claude reproduces, root-causes, and logs it here. **Resolve later** (this is a capture pass, not a fix pass). All LOCAL.

> Context: this walk follows Arc V (EFFORTLESS / cognitive-load) + Arc W (visual). Ian's standing concern: the previous arcs were partly assessed on the WRONG view (see Issue #1) and leaned on proxy recalibration rather than the real user experience — so we are now walking the ACTUAL live app, as a real user sees it.

---

## Issue #1 — Same user, different dashboard: hive context is NOT reset on user switch (stale tenant leak)

**Severity:** HIGH (multi-tenant correctness + "wrong/empty dashboard" UX + it invalidates session-reused UX audits).

**Symptom (observed live, 2026-06-25):** Signed in as **Pablo Aguilar** via `index.html`. My home showed **no hive chip**, an "All clear — nothing urgent" hero, and only **2 KPIs (6 Open Jobs · 2 Low Stock)**. Ian's WorkHive Tester, same Pablo, shows **Lucena Pharmaceutical Mfg.** with a **"TODAY · CRITICAL PM OVERDUE — Donaldson Pulse-Jet PJBH"** hero and **4 KPIs (19 Open Jobs · 6 Risk Alerts · 30 PM Overdue · 3 Low Stock)**.

**Evidence:**
- DB truth: `hive_members` → **Pablo Aguilar = supervisor of Lucena Pharmaceutical Mfg. (`3792d7f0-59e2-42e6-b04f-6e6ef4e4713d`), status active.** He is NOT a member of Baguio Textile Mills.
- My session `localStorage` after signing in as Pablo: `wh_last_worker="Pablo Aguilar"` ✓ but `hive_id="9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7"` (= **Baguio Textile Mills**) and `wh_hives=[{"name":"Baguio Textile Mills","role":"supervisor"}]`. Both are **leftover from the PREVIOUS session (Leandro Marquez, a Baguio supervisor)** — they were never cleared/re-resolved when Pablo signed in.
- Net: Pablo's session was pinned to a hive he doesn't belong to → RLS yields almost nothing → near-empty dashboard + the hive chip fails to render. The 6/2 KPIs are whatever leaked/defaulted, NOT Lucena's real numbers.

**Why it's happening (root cause — to confirm in code at fix time):** the sign-OUT path clears the auth token + `wh_last_worker` but does **not** clear the hive context (`wh_hives`, `hive_id`, and the hive-scoped caches like `wh_pm_recent_*`); and/or the sign-IN path does **not** re-fetch the new user's `hive_members` to overwrite `wh_hives`/`hive_id`. So a second user signing in on the same browser inherits the first user's active hive. The Tester masks this because it explicitly sets the correct hive when it provisions a session.

**Why it matters:**
1. **Multi-tenant leak / wrong tenant shown** — a user's session points at another tenant's hive id. On a **shared plant-floor tablet** (workers sign in/out all shift — the platform's literal use case) this is routine, not an edge case.
2. **Cognitive-load / trust** — the user lands on a wrong or empty dashboard ("All clear" when 30 PMs are overdue), which reads as "the app is broken / lost my data."
3. **Process integrity** — any automated UX/visual audit that reuses one browser session can silently analyze the WRONG hive's view. (Likely contaminated parts of the prior Arc V/W walks.)

**Repro:** sign in as user A (hive X) → Sign Out → sign in as user B (hive Y, different tenant) → B's home renders with hive X context (chip missing or wrong, KPIs wrong/empty).

**Fix direction (LATER):** on `signOut()` clear `wh_hives` + `hive_id` + all hive-scoped caches (`wh_pm_recent_*`, etc.); on `signIn()` always re-fetch the user's `hive_members` and set `hive_id` to their default/only active hive (and render the chip from that). Add a gate/journey: sign-in-as-B-after-A asserts `hive_id` == B's membership, never A's.

**★ DEEPER ROOT CAUSE (confirmed by DB + JWT + localStorage probes, 2026-06-25):** the DB is CORRECT — `auth.users` pabloaguilar = `644be73b-a406-4779-8895-51eab09ff30c`, and his `hive_members` row (Lucena, supervisor, active) carries `auth_uid = 644be73b` (properly linked). His JWT has **no hive claim** (`app_metadata` = provider/email only). Setting `localStorage.hive_id`/`wh_hives` to Lucena and reloading **did NOT change the home** (still 6/2, no chip) → **the home does not derive its KPIs/chip from `localStorage.hive_id` either.** So the real index.html login + home **never resolve the signed-in user's active hive from their (correct) `hive_members` row** on this path; only the WorkHive Tester provisions a session where the hive resolves. The data-layer is fine; the gap is **client-side session→hive resolution on the real front-door login**.

**★ DATA PROOF the wrong-view is real, not data drift:** live DB counts — **Lucena: 19 Open logbook + 3 low-stock** (EXACTLY Ian's Tester view 19/3 ✓ = the correct truth). **Baguio: 0 open.** My index-login session showed **6 Open / 2 Low** — which matches NEITHER hive → it is a wrong/fallback scope (likely Pablo's personal-assigned subset or a no-hive default), shown instead of his real hive. So a real user logging in through the front door sees the WRONG dashboard (and a dangerous "All clear" while 30 PMs are overdue).

**★ PROCESS IMPLICATION (ties to Ian's concern about the previous arcs):** every prior Arc V/W walk + screenshot used the journey/Tester `signIn` recipe, which DOES set the hive — so it NEVER exercised this real-login hive-resolution path. The visual/UX assessments were done on a session-shape real users don't get. The front-door login experience was never actually walked.

**★ EXACT KEYS (index.html:3494-3496, 3523):** the home computes `HIVE_ID = localStorage['wh_active_hive_id'] || localStorage['wh_hive_id']`, `HIVE_NAME = localStorage['wh_hive_name']`, `HIVE_ROLE = localStorage['wh_hive_role']`. If `HIVE_ID` is empty it runs **"Live (solo mode)"** and the tiles use a non-hive scope (the 6/2 fallback); the hive chip only renders when `HIVE_ID && HIVE_NAME`. The login flow never populates these from `hive_members`; the Tester does. (Note: my earlier attempt set `hive_id` + `wh_hives` — the WRONG keys — which is why it didn't move the view. Setting `wh_active_hive_id`/`wh_hive_id`/`wh_hive_name`/`wh_hive_role` to Lucena DID land the correct 19/6/30/3 view — confirming the diagnosis.)

**Fix direction (LATER):** (1) on the index.html login success, fetch the user's `hive_members` by `auth.uid()` and set the active hive (`wh_active_hive_id` + `wh_hive_id` + `wh_hive_name` + `wh_hive_role`) (default to their single/active membership), render the chip from it, and persist; (2) on `signOut`, clear `wh_hives`/`hive_id`/hive-scoped caches; (3) gate: a Playwright journey that signs in via the REAL index.html modal (not the recipe) and asserts the home chip + KPIs equal the user's DB hive truth (Pablo → Lucena 19/3), and that signing in as a second user never inherits the first's hive.

**★ CLEAN-SLATE CONFIRMATION (definitive):** cleared ALL localStorage + sessionStorage, then did a fresh front-door login as Pablo via the index.html modal → `wh_last_worker="Pablo Aguilar"` (auth OK) but `wh_hives=null`, `hive_id=null`, **no hive chip, KPIs 6/2** (not Lucena 19/3). So it is NOT stale leftover — **the real index.html login NEVER populates the hive context from the user's membership.** It only "works" when something external (the Tester) pre-sets it. This is a front-door bug every first-time real user would hit.

**Status:** LOGGED + root-caused + clean-slate-confirmed (capture pass). Not yet fixed — resolve later per Ian. To CONTINUE this walk on the correct view, sign in the way Ian does (WorkHive Tester) rather than the raw index.html modal.

---

## Issue #2 — The "act-on-it thread" breaks: a specific alert → a generic page (broken task continuity / deep-link)

**Severity:** HIGH · **Scope: CROSS-CUTTING — Ian: "it is common to all across all my feature pages."** (This is the issue-CLASS the new arc must generalize.)

**Symptom (observed live, Pablo @ Lucena, 2026-06-25):** The home's "Today's One Thing" hero said **"TODAY · CRITICAL PM OVERDUE — Donaldson Pulse-Jet PJBH: PM due — schedule the technician before the next shift"** with CTA **"Open PM Scheduler →"**. Clicking it navigates to **bare `pm-scheduler.html`** (no deep-link param) → the **full unfiltered list of 30 overdue PMs**. The Donaldson Pulse-Jet PJBH is just the **4th card in the list** — NOT pre-selected, highlighted, scrolled-to, or filtered — and there is no one-click "schedule the technician" for it on arrival.

**Why it's a cognitive-load defect (not just a missing nicety):** the alert did the hard cognitive work FOR the user — it identified the single most-urgent entity AND the next action. The CTA then **throws that context away**: the user must re-scan a 30-item list to re-find the exact asset the card just named, then re-derive the action. The interaction cost the alert promised to remove is **re-incurred at the destination**. Per NN/g Interaction Cost + Tesler's Law (complexity is conserved): the work didn't disappear, it moved to the user. This is the failure UFAI "floor=0" and the Arc V/W passes never caught — a flow can be "reachable + completable" and still **drop the thread** on every hand-off.

**Root-cause pattern:** CTAs/links/alerts/KPI tiles carry a **known entity id + intent** but emit a **scope-less href** (`pm-scheduler.html` instead of `pm-scheduler.html?asset=<id>&action=schedule` or an in-context action). The destination page can't pre-focus because the id never travels.

**Generalization (Ian's point):** this same "specific signal → generic destination" break almost certainly repeats across the platform — every KPI tile, risk alert, AMC-brief item, hive-board card, anomaly, low-stock warning, overdue badge that links to a list page rather than the specific record + action. **The new arc must (a) catch this class platform-wide deterministically, and (b) extend to the OTHER cognitive-load issue types it shares a family with.** → see `COGNITIVE_LOAD_II_ROADMAP.md` (being synthesized: skills-first → reputable sources → roadmap).

**Status:** LOGGED. This is issue #1 of "still so many other issues" Ian will surface — used as the seed exemplar for the Arc roadmap.
