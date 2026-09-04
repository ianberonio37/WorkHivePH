---
name: doc-PRODUCTION_DEPLOY_RUNBOOK
type: doc
source: file:PRODUCTION_DEPLOY_RUNBOOK.md
source_sha: 9f00a4d2040ad93c
last_verified: 2026-07-13
supersedes: null
---
## doc · PRODUCTION_DEPLOY_RUNBOOK

> **⏳ BUILT AND VERIFIED LOCALLY. NOT COMMITTED, NOT PUSHED, NOT DEPLOYED — Ian's gate.**

**Sections:** Production Deploy Runbook — page-bank walk + moderation/XP integrity (2026-08-20) ← PENDING, NOT DEPLOYED · 0. What ships · 0b. Added after the runbook was first written (2026-08-20, post-triage) · 0c. ★SECURITY — one NEW migration and two NEW gates, added after the suite triage (2026-08-20) · Migration count is now 11, not 10 · Extra post-deploy smoke (prod), on top of §5 · ★ Post-deploy smoke — COMPREHENSIVE (standing procedure, 2026-09-04) — SUPERSEDES the 5-flow §5 · PROD (post-deploy): · LOCAL rehearsal first (verify the smoke itself, against the running tester stack): · scope while triaging: --tier=public | --tier=app ; faster: --learn-sample=8 · 0d. ★FRONTEND — a lapsed session was DELETING the user's hive (2026-08-20) · 0e. GATE INTEGRITY — five validators were measuring PROSE, and one ratchet was loosening itself (2026-08-20) · 0f. 🔴 THE SUITE ITSELF COULD HANG FOREVER — `run_platform_checks.py` fixed (2026-08-20) · 0g. MARKETPLACE DIALOGS + the two CONTRAST gates finally proven (2026-08-20) · 0h. SUITE TRIAGE — what the 10 red gates actually were (2026-08-20, post-commit) · 0i. 🔴 LOCAL IS NOT A REHEARSAL OF LEG A — the local migration ledger stops at 2026-06-13 · 1. Pre-flight (all local, before any push) · The project is already linked (supabase/.temp/project-ref = hzyvnjtisfgbksicrouu) and there is NO · PROD_DB_URL in .env, so --linked is the form that actually runs. Verified 2026-08-20. · locate get_hive_dashboard in .tmp\prod_public.sql, diff its body against migration ...067 · 1b. Clean-run pre-flight — six gates failed, all six closed (2026-08-20) · 1c. Two ORDERING rules, both learned by tripping them in this release · 2. Leg A — DB · 3. Leg B — Edge (still on Z:) · NEW. A webhook: no session, authenticates by SVIX HMAC over the raw body, so --no-verify-jwt is · CORRECT here — the same reasoning as gcash-receipt-inbound. · (config.toml now ALSO declares [functions.resend-webhook-receiver] verify_jwt = false, added · 2026-08-20 after the Auto-discovery Validator caught the function missing from config entirely. · So the posture is durable: a later blanket deploy cannot silently flip it back to verify_jwt=true, · which would reject every Resend event.)

(Deep source: `file:PRODUCTION_DEPLOY_RUNBOOK.md` — retrieve this TOC to know WHICH section to read.)
