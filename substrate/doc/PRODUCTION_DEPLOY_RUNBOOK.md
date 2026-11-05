---
name: doc-PRODUCTION_DEPLOY_RUNBOOK
type: doc
source: file:PRODUCTION_DEPLOY_RUNBOOK.md
source_sha: af71e1289d1c6918
last_verified: 2026-07-13
supersedes: null
---
## doc · PRODUCTION_DEPLOY_RUNBOOK

> Ian, 2026-10-29, during the M3 release: *"why is it our gate is so rigid that we know in the first run that fails,

**Sections:** Release-gate cadence — one full run, then only what failed, then one final full run (standing, read before every milestone push) · M7 release (2026-11-05) - the shift's hand-offs (IN PROGRESS) · What a person using WorkHive will notice (release notes) · Leg A - DB: 6 migrations · Leg B - Edge: 2 functions · Leg C - Frontend · The touched-gate check (2026-11-05) - 17 reds, each at its cause · M6 release (2026-11-04) ✅ DEPLOYED · What a person using WorkHive will notice (release notes) · Leg A - DB: nothing to push · Leg B - Edge: 51 functions · 1. the four whose own source changed (copy only) · 2. the 46 that bundle _shared/tenant-context.ts (config.toml verify_jwt = false for each) · 3. WITHOUT the flag: config.toml verify_jwt = TRUE governs (the session is its gate; not in deploy-functions.ps1) · Leg C - Frontend: `workhive-shell-v589` · Post-deploy (production) · The release run, 2026-11-04 (main session) · Local pre-release checks, 2026-11-04 (static only, no browser, no board) · Resolve before the push · M5 release (2026-11-03) ✅ DEPLOYED · M4 release (2026-10-31) ✅ DEPLOYED · M3 release (2026-10-29) ✅ DEPLOYED · Production Deploy Runbook — M2 release (2026-10-28) ✅ DEPLOYED · M1 (2026-10-27) ✅ DEPLOYED · M1 release (2026-10-27) ✅ DEPLOYED · Production Deploy Runbook — release `27733934` (2026-10-23/24) ✅ DEPLOYED · Production Deploy Runbook — release `73335a30` + fixes `44bedbdd`, `d6b55009` (2026-10-16) ✅ DEPLOYED · Production Deploy Runbook — release `a2f9a45f` (2026-10-14) ✅ DEPLOYED · Production Deploy Runbook — release `ea9ed822` (2026-10-14) ✅ DEPLOYED · Production Deploy Runbook — release `c458e051` (2026-10-13) ✅ DEPLOYED · Production Deploy Runbook — release `15a5fd9f` (2026-09-29) ✅ DEPLOYED

(Deep source: `file:PRODUCTION_DEPLOY_RUNBOOK.md` — retrieve this TOC to know WHICH section to read.)
