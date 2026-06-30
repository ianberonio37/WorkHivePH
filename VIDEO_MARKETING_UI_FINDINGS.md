# Video Marketing UI/UX — Live Journey Findings & Revamp

**Created 2026-06-29 · Owner: Ian + Claude · Method: hands-on live MCP walk (operate-and-observe, intuition-gradient), not screenshot-judging.**

App: Flask single-page dashboard `video_marketing_app/app.py` + `templates/index.html` → **http://localhost:5001**. Walked live: landing → idea list → idea detail → **operated** Generate-ideas (6→11) → full generated script → Coverage Map. Governing question at each step: *"Does a non-expert operator understand what this is, why it's here, what to do next — and does it feel modern/trustworthy?"*

---

## ★ THE HEADLINE FINDING (P0 — strategic)

**F1 — The operator UI still drives the DATED pipeline; the new flagship engine is not wired in.**
Everything we just built (flagship spec → `render_flagship.py` → 9:16/1:1/16:9, product-as-hero, spring motion, mute-first, quality-gated, locked brand end card) has **no button in this UI**. Live evidence:
- "Auto-Produce Full Video" runs `script → narration → UI recording → scene clips → music → assemble` — the exact 2014 model (UI-recording PiP + TTS + stock scene) the revamp replaced.
- The generated **script panel** still emits "Runway Gen-4 / Kling AI" prompts, an "ElevenLabs Narration" block, and a **feature-listing** Solution (6 shots + a tacked-on "RIPPLE: Community Forum" second feature) — violating the 1-pain/1-feature rule the flagship enforces.
- "Branded BG" = the OLD Remotion sine-wave scenes, not `FlagshipReel`.
- **Verdict:** the single highest-leverage revamp is to **connect the UI to the flagship engine** — make "Produce Flagship Video" the primary action (generate FlagshipSpec → render 3 aspects + music + gate → show score + downloads), and retire/secondary the old assembler path. Until then the operator literally cannot make the new-style videos from the dashboard.

---

## ✅ BUILT (2026-06-29): P0 + score/preview wired into the dashboard
The dashboard now has a primary **"⚡ Produce Flagship Video"** lane (legacy assembler demoted) that runs the flagship engine (spec → `render_flagship` 9:16/1:1/16:9 → music → quality gate), with a dynamic-stage strip + **elapsed timer**, and on completion shows the **gate score (PASS 91.7)**, **3 download links**, and an **inline video preview**. Verified live end-to-end (idea_020). This resolves **F1** (UI now produces modern videos), **F13** (score surfaced), **F14** (in-UI preview), and the no-ETA part of **F12** (elapsed timer + per-aspect stages). Backend: `POST /api/ideas/<id>/produce-flagship` + `GET /api/flagship/<file>` in `app.py`; frontend `produceFlagship`/`pollFlagshipJob` in `index.html`.

## P1 — UX friction (observed live)

**F2 — CORRECTED / NOT A BUG.** I originally flagged "no loading feedback on Generate" — that was a mis-timed observation (I checked the button ~20s after click, *after* the ~15s call had finished and reverted). The code (`generateIdeas()`) **does** disable the button, show "Generating...", and toast "Calling AI to generate N ideas..." then revert in `finally`. Loading feedback is present. (Lesson: verify dynamic UI state *during* the action, not after.)

**F3 — Empty-half landing.** First impression is a large "🎬 Select an idea to get started" placeholder filling the entire right pane. No flow overview, no preview of a finished video, no quick-start for a first-time operator. → replace with a flow map (Idea → Script → Produce → Distribute), a "latest produced video" preview, or a guided start.

**F4 — Garbled / off-brand AI content ships unflagged.** The generated hook narration reads **"WorkHive: AI is taking jobs."** — i.e. it sounds like WorkHive is *announcing* AI takes jobs (brand-damaging). The script generator produces awkward hooks and adds a second feature ("RIPPLE"). → the flagship spec-gen already fixes this (1 pain, 1 feature, mute-first, no em dashes) — another reason to route authoring through it; at minimum add a human-readable warning + edit affordance.

**F5 — Duplicate, conflicting voice selectors.** The Auto-Produce card has a voice picker AND the collapsed "Manual steps" group exposes **two more** voice `<select>`s. Which one wins? → one source of truth for voice.

**F6 — Dense "production wall."** The Production Kit stacks Auto-Produce + a 6-step strip + NotebookLM long-form lane + Manual steps + Distribution as collapsed `▸` groups in one long scroll. The happy path is unclear amid the disclosure groups. → one clear primary action; push manual/long-form/distribution to clearly-secondary, collapsed-by-default, with a visible "advanced" label.

---

## P2 — bugs & polish

**F7 — CORRECTED / by-design, not a bug.** `GET /api/ideas/<id>/platform-pack` returns 404 ("Not generated yet") when no pack is cached; the frontend then POSTs to generate (GET-miss→POST pattern). The console line is cosmetic, not a failure. Optional nicety: return 204 to keep the console clean. Not fixing — it works as designed.

**F8 — CORRECTED / NOT a bug.** `checkHealth()` shows "Backlog running low" only when un-scripted (`status==='idea'`) ideas `<= 3`. At first load there were exactly 3 un-scripted (021/023/024) → correctly shown; after generating 5 more it correctly hid. My "shows with 11 ideas" was a mis-observation (counted total, not un-scripted). Working as intended.

**Verification status (honesty):** F2, F7, F8 were corrected to non-bugs after reading the code — glance-observation errors.

## ✅ CAREFUL LIVE-VERIFIED P1 PASS (2026-06-29) — result
Re-verified each P1 item by reading code / operating live, fixing only confirmed ones:
- **F3 — FIXED + verified live.** The empty "Select an idea" right-pane is now a **pipeline-flow overview** (💡 Idea → 📝 Script → ⚡ Flagship video → ⬇ Download + 8-platform pack) with the new flagship step highlighted + a one-line explainer. (`index.html` `welcomeState`.)
- **F10 — NOT a bug (graceful).** The Pexels/Jamendo "Auto-Download" buttons handle a missing key cleanly: clicking shows an inline "add your free key to .env / get free key →" message. Good degradation, not a dead action. (Optional: pre-label "needs key" — cosmetic.)
- **F5 — by-design, not a true duplicate.** The voice picker appears once in the (auto) Auto-Produce card and once in the (manual) per-step kit — two distinct lanes, each needs its own. (Minor: could share state.)
- **F12 — minor/inherent.** The legacy strip maps stage→index and polls every 1.5s, so it can lag the backend by a tick. The NEW flagship lane already shows per-aspect stages + an elapsed timer (better). Low value to chase on the legacy strip.
- **F9 — real but minor (open).** The Coverage Map opens as a 3rd column and crowds a 1440 viewport; better as an overlay/drawer. Low-value polish; not yet done.

**Net of the pass:** the substantive problem (F1) is fixed by the P0 build; the real UX gaps (F3 empty landing, F13 score, F14 preview) are fixed; F2/F7/F8/F10 were not bugs and F5 is by-design. Only F9 (minor layout) and F11 (subjective labels) remain as optional polish. The pass's value was the verification — most "findings" were glance-noise, exactly what operate-and-verify is meant to catch.

**F9 — Coverage Map crowds the layout.** Toggling it inserts a 3rd dense column on a 1440 viewport, shrinking everything; the per-feature list is long with tiny status badges. → make it an overlay/drawer or a compact summary with drill-down.

**F10 — Dead-key actions presented as live.** Pexels (scene) and Jamendo (music) stages are surfaced as actions but 400 with `needs_key` (no keys in `.env`). → hide or pre-label "needs API key." (The flagship engine sidesteps both: cached `.tmp/music/` bed + Remotion scenes — another reason to make it primary.)

**F11 — Ambiguous controls.** "Reload Script" (vs View/Edit) and the clickable pipeline-stage stepper (does a click *navigate* or *change status*?) read ambiguously. → clearer labels + a confirm on destructive status moves.

---

## Recommended revamp order
1. **(P0) Wire the UI to the flagship engine** — a "Produce Flagship Video" primary action: FlagshipSpec → `render_flagship` (9:16/1:1/16:9 + music + SFX + quality gate) → show the **gate score** + 3 download links. Make modern output the default; demote the old assembler.
2. **(P1) Loading states** on every AI/render action (disable + spinner + progress/toast).
3. **(P1) Declutter** the production wall to one happy path; **dedupe** the voice pickers.
4. **(P1) Fix the empty landing** (flow map + latest-video preview).
5. **(P2) Fix the 404, the "backlog low" copy, the dead-key actions, the Coverage Map layout, ambiguous labels.**

---

## PRODUCE-RUN LIVE WALK (operated end-to-end, idea_019)

Ran **Auto-Produce** on idea_019 to completion (~5-6 min). Backend chain (from the job log `job_idea_019_cc0d57d2`): `script → voice (Edge-TTS James) → storyboard (13 beats) → UI recording (Playwright on the live WorkHive site) → scene (OLD Remotion storyboard mp4) → music (KraftiM) → assemble (FFmpeg+Whisper) → 9:16 vertical → creative gate 100/100 → platform_pack → done`. The UI showed a 6-step strip animating to all ✓ and a **"Download 3.4MB MP4"** link at the end.

What the hands-on run confirmed (adds to / sharpens the findings above):

- **F1 CONFIRMED at the source.** The produce path itself builds the DATED video: a **13-beat storyboard jumping across 4 features** (`alert_hub → resume_builder → achievements → community`) = the feature-listing anti-pattern the flagship explicitly fixes (1 pain, 1 feature); UI-recording-PiP + TTS + the OLD Remotion sine-wave storyboard + generic stock music. **This is where the dated output is generated — so the P0 fix (route produce-all through the flagship engine) is exactly the right cut, not just a cosmetic UI swap.**
- **F12 — coarse, laggy progress on a multi-minute job.** Each stage is a pulsing dot with no sub-progress / % / ETA / elapsed; Scene and Assemble are each multi-minute, and the **UI strip lagged the backend** (showed "Scene active" while the backend was already on "assemble"). On a 5-6 min run a user can't tell if it's stuck. → per-stage progress + elapsed/ETA, and a clear "this takes a few minutes" expectation.
- **F13 — misleading "100/100 PASS" + score not surfaced.** The produce gate scored the OLD storyboard structure **100/100 (PASS)** — but the actual video is the dated PiP/TTS style. The gate validates *structure*, not *modern visual quality*, so a green score masks a dated result. And the score from the log is **not shown in the UI** at all (only the download link). → surface the score in the UI AND make the gate reflect the flagship bar.
- **F14 — no in-UI preview.** Completion gives a "Download MP4" link but no inline player to watch the result before downloading.
- **Positive:** the produce flow DOES give end-state feedback (6 ✓ + download link) — better than the Generate step (F2). Edge-TTS narration, UI recording (on the live WorkHive site), and assembly all ran without keys.

**Net:** the live produce walk validates the strategy — the **single highest-leverage move is to re-point `produce-all` (and the script step) at the flagship engine** (`flagship` spec → `render_flagship`), which simultaneously fixes the dated output (F1), the feature-listing (F1), and makes the 100/100 gate meaningful (F13). UI polish (F2/F12/F13/F14) layers on top.

**Still not walked live:** NotebookLM long-form campaign, the manual piecemeal assemble lane.
