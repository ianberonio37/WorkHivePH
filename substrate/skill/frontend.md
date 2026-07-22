---
name: skill-frontend
type: skill
source: skill:frontend
source_sha: e7b30f537c5aa3db
last_verified: 2026-07-13
supersedes: null
---
## skill · frontend

Builds UI from specs — HTML, CSS, vanilla JS, animations, responsive layouts. Triggers on "build the UI", "CSS", "animation", "responsive", "layout", "component", "design".

**Sections:** Frontend Agent · Every async WRITE-submit button MUST be single-flight-locked (2026-07-21) · Validate user input BEFORE the write, not after (2026-07-21) · A number input's `min`/`step` is NOT enforced on a button-submit path — parse via central `whParseQty`, never bare `parseFloat()||0` (2026-07-22, DEEPWALK D5) · A shared render fn owning BOTH empty-state and no-results must make the `.length===0` branch VIEW-AWARE for a server-filtered list (2026-07-22, DEEPWALK D3) · Your Responsibilities · How to Operate · This Platform's Context · Grounded UFAI-Sweep a11y lessons (2026-06-07, index.html) · Per-page EN/FIL i18n recipe + its gate-sweep (2026-07-15, home dashboard N1) · Whole-page state-switch: chrome OUTSIDE the hidden wrapper LEAKS (2026-07-15, home dashboard L1) · Silent-zero display fallbacks — `_orNA` for a value that can never legitimately be 0 (2026-07-09, eng-design F-5/G1) · Coding Standards · Canonical Globals — May 2026 Null Guard Pattern · getElementById Safety Rules · Use `?.` for any element that might be absent · After any form refactor — audit getElementById IDs in save/submit functions · Multi-Step Flow State Management · Confirmation Feedback for Linked Entities · Mutation Functions — Internal Role Guard Required · Async Refactor — Immediate Call Site Audit · Plotly Charts in Collapsed Cards — Lazy Init or Resize on Expand · Plotly Y-Axis Auto-Inverts for Decreasing Data · Auto-learned (2026-07-12 — PM Scheduler PDDA) · Lessons from Production (April 2026 — Report Sender build) · Supabase CDN script is required on every page that calls supabase.createClient() · A read of a NEVER-ASSIGNED global is a silent DEAD PATH — the `if (global)` guard is always false (2026-07-08, CL8) · Modal/sheet HTML must be placed BEFORE the `<script>` block · `setTimeout` proximity to `forEach` triggers timer validator · `Promise.allSettled` for all parallel async operations

(Deep source: `skill:frontend` — retrieve this TOC to know WHICH section to read.)
