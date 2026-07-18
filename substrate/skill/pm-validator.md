---
name: skill-pm-validator
type: skill
source: skill:pm-validator
source_sha: 83d49d50bf1d9cb6
last_verified: 2026-07-13
supersedes: null
---
## skill · pm-validator

Static analysis of `pm-scheduler.html` covering the six correctness properties of the

**Sections:** PM Validator Skill · What This Is · When to Run · What It Checks · [1] FREQ_DAYS Alignment with Frequency Options · [2] PM_TEMPLATES Coverage in PM_CAT_TO_LOG_CAT · [3] PM_CAT_TO_LOG_CAT Values are Valid Logbook Categories · [4] compPayload Required Fields · [5] scopePayload Required Fields · [6] Due Date Midnight Normalisation · Baseline Result (April 2026) · Adding a New Frequency · Auto-learned (2026-04-27) · Auto-learned (2026-07-12 — PM Scheduler PDDA arc) · Check [1] repurposed → `freq_render_robust` (was `freq_days_alignment`, now moot) · Three cross-hive write holes (I-axis keystone) — migration `20260712000012`, gate `validate_pm_write_isolation.py` · Reschedule loop is view-driven (verify, don't rebuild) · AI grounding + worst-first triage · Ratchet-reconciliation is part of the LOCK spoke (render-budget + sentinel trip when you add code/validators) · The freq-vocabulary class REPEATS cross-page — sweep every PM-frequency-displaying surface

(Deep source: `skill:pm-validator` — retrieve this TOC to know WHICH section to read.)
