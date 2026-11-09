---
name: doc-PRODUCTION_DEPLOY_RUNBOOK
type: doc
source: file:PRODUCTION_DEPLOY_RUNBOOK.md
source_sha: 5f4e001409222753
last_verified: 2026-07-13
supersedes: null
---
## doc · PRODUCTION_DEPLOY_RUNBOOK

> Ian, 2026-10-29, during the M3 release: *"why is it our gate is so rigid that we know in the first run that fails,

**Sections:** Release-gate cadence — one full run, then only what failed, then one final full run (standing, read before every milestone push) · M12 release (2026-11-08) - what the critic found on signed-in screens · What a person using WorkHive will notice (release notes) · The touched gates this release reached (`--rerun-failed`, 633 gates) · M11 release (2026-11-07) - the group's UX face ✅ DEPLOYED · What a person using WorkHive will notice (release notes) · The skipped gates this release reaches (`tools/skipped_gates_for_diff.py`) · M10 release (2026-11-06) - founder and public hand-offs ✅ DEPLOYED · What a person using WorkHive will notice (release notes) · M9 release (2026-11-06) - marketplace, onboarding and integrations ✅ DEPLOYED · What a person using WorkHive will notice (release notes) · M8 release (2026-11-05) - the record's hand-offs ✅ DEPLOYED · What a person using WorkHive will notice (release notes) · Leg A - DB: 5 migrations · Leg B - Edge: 1 function · Leg C - Frontend · M7 release (2026-11-05) ✅ DEPLOYED · What a person using WorkHive will notice (release notes) · Leg A - DB: 6 migrations · Leg B - Edge: 2 functions · Leg C - Frontend · The touched-gate check (2026-11-05) - 17 reds, each at its cause · M6 release (2026-11-04) ✅ DEPLOYED · What a person using WorkHive will notice (release notes) · Leg A - DB: nothing to push · Leg B - Edge: 51 functions · 1. the four whose own source changed (copy only) · 2. the 46 that bundle _shared/tenant-context.ts (config.toml verify_jwt = false for each) · 3. WITHOUT the flag: config.toml verify_jwt = TRUE governs (the session is its gate; not in deploy-functions.ps1) · Leg C - Frontend: `workhive-shell-v589`

(Deep source: `file:PRODUCTION_DEPLOY_RUNBOOK.md` — retrieve this TOC to know WHICH section to read.)
