---
name: doc-PRODUCTION_DEPLOY_RUNBOOK
type: doc
source: file:PRODUCTION_DEPLOY_RUNBOOK.md
source_sha: ba84afabbf285c97
last_verified: 2026-07-13
supersedes: null
---
## doc · PRODUCTION_DEPLOY_RUNBOOK

> Ian, 2026-10-29, during the M3 release: *"why is it our gate is so rigid that we know in the first run that fails,

**Sections:** Release-gate cadence — one full run, then only what failed, then one final full run (standing, read before every milestone push) · M9 release (2026-11-06) - marketplace, onboarding and integrations · What a person using WorkHive will notice (release notes) · M8 release (2026-11-05) - the record's hand-offs ✅ DEPLOYED · What a person using WorkHive will notice (release notes) · Leg A - DB: 5 migrations · Leg B - Edge: 1 function · Leg C - Frontend · M7 release (2026-11-05) ✅ DEPLOYED · What a person using WorkHive will notice (release notes) · Leg A - DB: 6 migrations · Leg B - Edge: 2 functions · Leg C - Frontend · The touched-gate check (2026-11-05) - 17 reds, each at its cause · M6 release (2026-11-04) ✅ DEPLOYED · What a person using WorkHive will notice (release notes) · Leg A - DB: nothing to push · Leg B - Edge: 51 functions · 1. the four whose own source changed (copy only) · 2. the 46 that bundle _shared/tenant-context.ts (config.toml verify_jwt = false for each) · 3. WITHOUT the flag: config.toml verify_jwt = TRUE governs (the session is its gate; not in deploy-functions.ps1) · Leg C - Frontend: `workhive-shell-v589` · Post-deploy (production) · The release run, 2026-11-04 (main session) · Local pre-release checks, 2026-11-04 (static only, no browser, no board) · Resolve before the push · M5 release (2026-11-03) ✅ DEPLOYED · M4 release (2026-10-31) ✅ DEPLOYED · M3 release (2026-10-29) ✅ DEPLOYED · Production Deploy Runbook — M2 release (2026-10-28) ✅ DEPLOYED · M1 (2026-10-27) ✅ DEPLOYED

(Deep source: `file:PRODUCTION_DEPLOY_RUNBOOK.md` — retrieve this TOC to know WHICH section to read.)
