---
name: doc-PRODUCTION_DEPLOY_RUNBOOK
type: doc
source: file:PRODUCTION_DEPLOY_RUNBOOK.md
source_sha: 62495102f3b643f9
last_verified: 2026-07-13
supersedes: null
---
## doc · PRODUCTION_DEPLOY_RUNBOOK

> **⏳ BUILT AND VERIFIED LOCALLY. NOT COMMITTED, NOT PUSHED, NOT DEPLOYED — Ian's gate.**

**Sections:** Production Deploy Runbook — page-bank walk + moderation/XP integrity (2026-08-20) ← PENDING, NOT DEPLOYED · 0. What ships · 0b. Added after the runbook was first written (2026-08-20, post-triage) · 0c. ★SECURITY — one NEW migration and two NEW gates, added after the suite triage (2026-08-20) · Migration count is now 11, not 10 · Extra post-deploy smoke (prod), on top of §5 · 0d. ★FRONTEND — a lapsed session was DELETING the user's hive (2026-08-20) · 0e. GATE INTEGRITY — five validators were measuring PROSE, and one ratchet was loosening itself (2026-08-20) · 0f. 🔴 THE SUITE ITSELF COULD HANG FOREVER — `run_platform_checks.py` fixed (2026-08-20) · 0g. MARKETPLACE DIALOGS + the two CONTRAST gates finally proven (2026-08-20) · 0h. SUITE TRIAGE — what the 10 red gates actually were (2026-08-20, post-commit) · 1. Pre-flight (all local, before any push) · The project is already linked (supabase/.temp/project-ref = hzyvnjtisfgbksicrouu) and there is NO · PROD_DB_URL in .env, so --linked is the form that actually runs. Verified 2026-08-20. · locate get_hive_dashboard in .tmp\prod_public.sql, diff its body against migration ...067 · 1b. Clean-run pre-flight — six gates failed, all six closed (2026-08-20) · 1c. Two ORDERING rules, both learned by tripping them in this release · 2. Leg A — DB · 3. Leg B — Edge (still on Z:) · NEW. A webhook: no session, authenticates by SVIX HMAC over the raw body, so --no-verify-jwt is · CORRECT here — the same reasoning as gcash-receipt-inbound. · (config.toml now ALSO declares [functions.resend-webhook-receiver] verify_jwt = false, added · 2026-08-20 after the Auto-discovery Validator caught the function missing from config entirely. · So the posture is durable: a later blanket deploy cannot silently flip it back to verify_jwt=true, · which would reject every Resend event.) · The other 10 are ALREADY IN deploy-functions.ps1 and the script's blanket --no-verify-jwt AGREES · with config.toml, which declares verify_jwt = false for each of them (checked 2026-08-20, not · assumed — an earlier draft of this runbook said to avoid the script, which was wrong: both paths · produce the same posture here). So run the script, or deploy individually; the result is identical. · .\deploy-functions.ps1

(Deep source: `file:PRODUCTION_DEPLOY_RUNBOOK.md` — retrieve this TOC to know WHICH section to read.)
