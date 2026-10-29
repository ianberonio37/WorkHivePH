---
name: doc-PRODUCTION_DEPLOY_RUNBOOK
type: doc
source: file:PRODUCTION_DEPLOY_RUNBOOK.md
source_sha: d83c244dfac4d725
last_verified: 2026-07-13
supersedes: null
---
## doc · PRODUCTION_DEPLOY_RUNBOOK

> Ian, 2026-10-29, during the M3 release: *"why is it our gate is so rigid that we know in the first run that fails,

**Sections:** Release-gate cadence — one full run, then only what failed, then one final full run (standing, read before every milestone push) · M3 release (2026-10-29) ✅ DEPLOYED · Production Deploy Runbook — M2 release (2026-10-28) ✅ DEPLOYED · M1 (2026-10-27) ✅ DEPLOYED · M1 release (2026-10-27) ✅ DEPLOYED · Production Deploy Runbook — release `27733934` (2026-10-23/24) ✅ DEPLOYED · Production Deploy Runbook — release `73335a30` + fixes `44bedbdd`, `d6b55009` (2026-10-16) ✅ DEPLOYED · Production Deploy Runbook — release `a2f9a45f` (2026-10-14) ✅ DEPLOYED · Production Deploy Runbook — release `ea9ed822` (2026-10-14) ✅ DEPLOYED · Production Deploy Runbook — release `c458e051` (2026-10-13) ✅ DEPLOYED · Production Deploy Runbook — release `15a5fd9f` (2026-09-29) ✅ DEPLOYED · Production Deploy Runbook — release `ffca85f1` (2026-09-11) ✅ DEPLOYED · Production Deploy Runbook — release `6fab5624` (2026-09-04) ✅ DEPLOYED · Production Deploy Runbook — page-bank walk + moderation/XP integrity (2026-08-20) ← PENDING, NOT DEPLOYED · 0. What ships · 0b. Added after the runbook was first written (2026-08-20, post-triage) · 0c. ★SECURITY — one NEW migration and two NEW gates, added after the suite triage (2026-08-20) · Migration count is now 11, not 10 · IndexNow push — a standing post-deploy step (Wave KA, 2026-10-26) · Extra post-deploy smoke (prod), on top of §5 · ★ Post-deploy smoke — COMPREHENSIVE (standing procedure, 2026-09-04) — SUPERSEDES the 5-flow §5 · PROD (post-deploy): · LOCAL rehearsal first (verify the smoke itself, against the running tester stack): · scope while triaging: --tier=public | --tier=app ; faster: --learn-sample=8 · 0d. ★FRONTEND — a lapsed session was DELETING the user's hive (2026-08-20) · 0e. GATE INTEGRITY — five validators were measuring PROSE, and one ratchet was loosening itself (2026-08-20) · 0f. 🔴 THE SUITE ITSELF COULD HANG FOREVER — `run_platform_checks.py` fixed (2026-08-20) · 0g. MARKETPLACE DIALOGS + the two CONTRAST gates finally proven (2026-08-20) · 0h. SUITE TRIAGE — what the 10 red gates actually were (2026-08-20, post-commit) · 0i. 🔴 LOCAL IS NOT A REHEARSAL OF LEG A — the local migration ledger stops at 2026-06-13 · 1. Pre-flight (all local, before any push)

(Deep source: `file:PRODUCTION_DEPLOY_RUNBOOK.md` — retrieve this TOC to know WHICH section to read.)
