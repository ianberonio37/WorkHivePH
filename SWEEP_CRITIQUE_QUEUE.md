# Grounded MCP Sweep — Critique Queue (harsh critic, you DISPOSE)

> **Human-readable mirror.** The machine feed is `sweep_critiques.json`, which
> `flywheel_orchestrator.py` now reads into **`promotion_queue.md`** each turn as a
> dedicated "Grounded MCP Sweep critiques" section — so these flow through the SAME
> self-improving-gate promotion engine + disposition mechanism as the substrate miner
> (they are NOT recurrence-gated; a deliberate finding is valid the first turn raised).
> Keep the two in sync when adding a critique.
>
> Doctrine: **the sweep discovers and drafts; YOU judge; nothing is auto-applied.**
> Each row CITES what it's measured against (a skill rule, a UX law, a standard, a
> pillar, or a sibling page) and flags **DEFECT** / **TASTE** / **CONTENT**.
>
> To dispose: record `{status: approved|rejected|snoozed}` against the key in
> `promotion_dispositions.json` (same mechanism as the main queue) — it then drops
> off both this file's intent and the generated `promotion_queue.md`.
> A CONFORMANCE bug is fixed inline by the sweep (see the page worksheet §4); only
> these "should-be" design/IA calls wait for you.
>
> **Note on C7:** a forward-only gate ratchet (`validate_modal_a11y.py`, debt baseline
> = 13) now ENFORCES "no NEW hand-rolled modal without role=dialog+aria-modal". C7
> below is the remaining *retrofit of existing debt* (the shared `whModalA11y` helper);
> approving it ratchets the baseline down.

---

## ✅ DISPOSITIONED — 2026-06-07 (all 24, by owner)

> **Source of truth: `promotion_dispositions.json`.** All 24 sweep critiques are
> dispositioned (**23 approved · 1 rejected**) and have dropped off `promotion_queue.md`.
> They collapse into **6 root-cause work items** (none auto-applied — these are now the
> accepted backlog, awaiting implementation):
>
> - **W1 · Platform tap-target base rule** (collapses 13): one `.wh-tappable`
>   `min-height:44px` on every interactive role (button/[role=button]/tab/chip/pill/icon-btn)
>   + extend `validate_mobile` to compute **per-element box size** (closes the inline-only
>   BLIND SPOT #1/#2 that let these slip page-after-page). Owner rule: **44px everywhere,
>   NO exceptions** — filter-chips (pm-scheduler 32→44, voice-journal 36→44) included.
> - **W2 · Modal-a11y retrofit** (collapses 4): shared `whModalA11y(modalEl)` helper +
>   widen `validate_modal_a11y.py` to catch inline `position:fixed;inset:0` modals + retrofit
>   pm-edit-modal / dayplanner modal. Ratchets the C7 debt baseline (13) down.
> - **W3 · Status-enum drift guard**: shared per-table status-enum JS constant + a validator
>   that greps filter string-literals against the DB enum (the dayplanner overdue KPI bug class).
> - **W4 · Index a11y**: pwd-reveal keyboard reach (WCAG 2.1.1) + auth-tabs ARIA pattern.
> - **W5 · `window.WHShell` read-seam** (low-priority, cross-page parity with `WHResume`).
> - **W6 · Judgment**: #5 first-action alignment → **APPROVED** (align verdict+CTA+ladder on
>   ONE zero-data activation, suggested "Log your first job"); #6 landing CTA density →
>   **REJECTED** (won't-fix; the critic itself called it likely-fine for a marketing landing).

---

## Wave 0 — `index.html` (the shell / front door)  ·  2026-06-06

### C1 · No `window.WHShell` test seam
- **key:** `sweep:index:whshell-seam`
- **Now:** the shell's state (which mode — landing vs dashboard — plus identity/role) is only reachable by poking the DOM + localStorage. Globals exist (`_initDashboard`, `openSignIn`, `signOut`) but there is no read-seam.
- **Should be:** expose a tiny read-only `window.WHShell = { mode(), identity(), role() }`.
- **Where:** `index.html`.
- **Why:** testability + recognition-over-recall for future sweep authors; **sibling `resume.html` already exposes `window.WHResume`** (cross-page consistency is a contract).
- **Pillar:** Internal Control · **Sev:** Minor · **Eff:** S · **Flag:** TASTE (maintainability, not user-facing).
- [x] dispose → DISPOSITIONED 2026-06-07 (see banner ↑ / `promotion_dispositions.json`)

### C2 · Password-reveal eye buttons are `tabindex="-1"`
- **key:** `sweep:index:pwd-reveal-keyboard`
- **Now:** all three show/hide-password toggles (`index.html:2509, 2546, 2555`) carry `tabindex="-1"` → keyboard-only users cannot reveal what they typed.
- **Should be:** make them keyboard-reachable (drop the `-1`, keep them last in the field's tab order) OR replace with a labelled "Show password" checkbox.
- **Why:** WCAG 2.1.1 (keyboard operability). Note: skipping reveal toggles in tab order is a *common* deliberate pattern — hence your call.
- **Pillar:** Usability/IC · **Sev:** Minor · **Eff:** S · **Flag:** DEFECT (a11y), mild.
- [x] dispose → DISPOSITIONED 2026-06-07 (see banner ↑ / `promotion_dispositions.json`)

### C3 · Auth modal tabs lack the ARIA tab pattern
- **key:** `sweep:index:auth-tabs-aria`
- **Now:** `#tab-signin` / `#tab-signup` are plain `<button>`s; a screen reader does not announce a tablist or which tab is selected. (The dialog now has `role="dialog"` + `aria-modal` from the sweep fix, but the inner tabs are unmarked.)
- **Should be:** `role="tablist"` on the wrapper, `role="tab"` + `aria-selected` on each button, `role="tabpanel"` + `aria-labelledby` on each panel.
- **Why:** WAI-ARIA Authoring Practices — Tabs pattern.
- **Pillar:** Usability · **Sev:** Minor · **Eff:** M · **Flag:** DEFECT (a11y).
- [x] dispose → DISPOSITIONED 2026-06-07 (see banner ↑ / `promotion_dispositions.json`)

### C4 · Onboarding-ladder items are 42px tall on mobile
- **key:** `sweep:index:onboarding-ladder-44`
- **Now:** the `#oh-onboarding` ladder links ("Set your name", "Join a hive…") measure h=42 at TRUE-390 — 2px under the gloved-hand minimum. (The sweep already lifted the header Sign In/hamburger/Sign Out/persona controls to 44px; these secondary ladder items were left as a judgment call.)
- **Should be:** extend the mobile `min-height:44px` rule to the ladder items.
- **Why:** mobile-maestro 44px tap minimum (field workers, gloves).
- **Pillar:** Usability · **Sev:** Polish · **Eff:** S · **Flag:** DEFECT (minor).
- [x] dispose → DISPOSITIONED 2026-06-07 (see banner ↑ / `promotion_dispositions.json`)

### C5 · First-run solo "next step" points three different ways
- **key:** `sweep:index:first-action-alignment`
- **Now:** a brand-new solo user (zero data) sees: verdict → "Plan your shift in the **Day Planner**"; primary CTA → "**Log a Job**"; onboarding ladder → "Set your name / Join a hive". Three competing "first steps".
- **Should be:** align on ONE activating first action. For a zero-data novice the data-creating act ("Log your first job") is the natural activation; make the verdict, primary CTA, and ladder agree (or sequence them).
- **Where:** `index.html` `_initDashboard` verdict/actions + onboarding ladder.
- **Why:** onboarding best practice (a single clear first action) + Hick's law (reduce competing choices at the decisive moment).
- **Pillar:** Usability/IA · **Sev:** Minor · **Eff:** M · **Flag:** TASTE/IA.
- [x] dispose → DISPOSITIONED 2026-06-07 (see banner ↑ / `promotion_dispositions.json`)

### C6 · Landing shows 57 visible CTAs at 390px
- **key:** `sweep:index:landing-cta-density`
- **Now:** 57 visible interactive elements on the logged-out landing at TRUE-390.
- **Should be:** likely FINE — a marketing landing legitimately funnels many entry points to one signup. Logged here only for honesty; not recommending a change without a conversion goal.
- **Why:** Hick's law (more choices = slower decisions) — but weighed against marketing-page norms (Jakob's law).
- **Pillar:** Usability · **Sev:** Polish · **Eff:** L · **Flag:** TASTE (likely a non-issue).
- [x] dispose → DISPOSITIONED 2026-06-07 (see banner ↑ / `promotion_dispositions.json`)

---

## Wave 1 — `logbook.html`  ·  2026-06-06

### C7 · Hand-rolled modals lack the dialog a11y bar — PLATFORM-WIDE (shared-helper rec)
- **key:** `sweep:platform:modal-a11y-helper`
- **Now:** `logbook.html` has **8 hand-rolled modals** (`#modal`, `#asset-modal`, `#asset-edit-modal`, `#asset-detail-modal`, `#asset-picker-modal`, `#tasklist-modal`, `#parts-picker-modal`, …) — NONE declare `role="dialog"`/`aria-modal`, and the page has **zero ESC/keydown handling** (no ESC-close, no focus-trap, no focus-restore). The same gap was found+fixed inline on `index.html`'s sign-in modal (Wave 0). This is now confirmed SYSTEMIC: hand-rolled modals across the platform skip the a11y contract that `utils.js` `whConfirm`/`whPrompt` already model. (Their close buttons ARE good: 44px `w-11 h-11` + `aria-label="Close"`.)
- **Should be:** a shared **`whModalA11y(modalEl, { onClose, labelledBy })`** helper (or a `data-wh-modal` mixin) that, for any element it's attached to, sets `role="dialog"`+`aria-modal="true"`+an accessible name, wires ESC-to-close, traps Tab within the shown panel, and restores focus to the opener — then retrofit every hand-rolled modal to call it. ONE implementation, applied platform-wide, instead of N ad-hoc per-page handlers that drift.
- **Where:** new `_shared`/`utils.js` helper + retrofits on logbook.html (8), index.html (already inline — migrate to the helper for consistency), and every other page with hand-rolled modals (a sweep-wide audit item).
- **Why:** WCAG dialog pattern + Jakob's law (the platform ALREADY has the bar in whConfirm/whPrompt — hand-rolled modals must match it) + this is the interconnection web applied to a11y: a shared control should have a shared, correct implementation.
- **Pillar:** Usability/Internal Control · **Sev:** Major (a11y, every modal-using page) · **Eff:** M–L · **Flag:** DEFECT.
- **NOTE:** routed (not auto-applied) because retrofitting 8 logbook modals + their open/close fns blind, while the user is away, is exactly the kind of broad rewrite the critic PROPOSES and the owner DISPOSES. The Wave-0 shell modal was fixed inline because it was a single, contained, high-traffic dialog.
- [x] dispose → DISPOSITIONED 2026-06-07 (see banner ↑ / `promotion_dispositions.json`)

### C8 · `voice-fill-btn` "Speak" / `vdc-capture-btn` "Capture" rely on min-h with no explicit type
- **key:** `sweep:logbook:voice-btn-consistency`
- **Now:** after the Voice Journal `min-h-[44px]` fix, the remaining header actions all carry `min-h-[44px]` and pass. Minor consistency nit: the voice/capture buttons size purely via `min-h-[44px]` utility; if a future refactor drops the utility they silently shrink (the exact failure mode that hit Voice Journal).
- **Should be:** consider a shared `.btn-tap` class (min-height:44px baked in) for all header action buttons so a dropped utility can't regress tap size — and a static lint that `btn-secondary`/`btn-primary` action buttons declare a 44px floor.
- **Why:** mobile-maestro 44px + defence-in-depth (don't let tap size depend on remembering a utility class on every instance).
- **Pillar:** Usability · **Sev:** Minor · **Eff:** S · **Flag:** TASTE/hardening.
- [x] dispose → DISPOSITIONED 2026-06-07 (see banner ↑ / `promotion_dispositions.json`)

## Wave 1 — `inventory.html`  ·  2026-06-06

### C9 · `style="min-height:unset"` is a recurring anti-pattern that defeats the 44px default
- **key:** `sweep:inventory:min-height-unset-antipattern`
- **Now:** `.btn-primary`/`.btn-secondary` ship `min-height:44px` by default, but several inventory controls override it with an inline `style="min-height:unset"`: the primary "Add Part" CTA (FIXED inline this sweep — it was 32px on a field phone), the "Back to Basic Worker" link (`:237`), and the 7 per-row "Open item details" icon buttons (`:941`, `p-1` → 24px; these DO carry `aria-label="Open item details"`, so name is fine — only size). Inline `min-height:unset` can't be re-raised by a mobile media query (inline wins), so each instance is a silent sub-44 tap target.
- **Should be:** (a) the row icon buttons → either bump to 44px or guarantee the whole row is a ≥44px hit target (then the icon is a redundant affordance, acceptable); (b) platform-wide, treat `style="min-height:unset"` on a `.btn-*` as a lint smell — if a control must be compact on desktop, do it with a mobile-restoring media query, not an inline unset that bites phones.
- **Where:** inventory.html row template + a cross-page grep for `min-height:unset` on `.btn-*` (likely recurs elsewhere — a sweep-wide audit item).
- **Why:** mobile-maestro 44px (gloved field workers) + the inline-style-beats-media-query trap.
- **Pillar:** Usability · **Sev:** Minor–Major (row icons are frequent) · **Eff:** M · **Flag:** DEFECT (entangled with a deliberate compact-row choice → owner disposes the row-icon call).
- [x] dispose → DISPOSITIONED 2026-06-07 (see banner ↑ / `promotion_dispositions.json`)
