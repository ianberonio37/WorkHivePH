---
name: doc-PRODUCTION_DEPLOY_RUNBOOK
type: doc
source: file:PRODUCTION_DEPLOY_RUNBOOK.md
source_sha: b9b4b58b997a73b6
last_verified: 2026-07-13
supersedes: null
---
## doc · PRODUCTION_DEPLOY_RUNBOOK

**Owner: Ian (all outward steps are Ian-gated).** Claude prepared + pre-flighted this; the three

**Sections:** Production Deploy Runbook — accumulated release (2026-07-06) · 0. What ships in this release (the true scope) · Headline content · 1. Leg A — DB migrations · From the repo root. The "&" in the folder name breaks `npx supabase`, so subst a clean drive first · (memory: feedback_deploy_subst). · 1a. CONFIRM the 14 are remote-pending (not already applied out-of-band): · 1b. Push: · 2. Leg B — Edge functions · Still on Z:.  Run the existing script (54 fns): · +2 modified fns MISSING from the script. Deploy them SEPARATELY (NOT via the script) because the · script forces --no-verify-jwt on all 54, which is WRONG for the reset fn. Let config.toml govern: · −5 deleted Stripe marketplace fns (delete from prod; db push does NOT remove these): · 3. Leg C — Frontend (Netlify) · 4. Rollback · 5. Pre-flight gate result · 5a. FIXED + verified green (8) — all deployable-code issues · 5b. Remaining FAILs — NOT deployable-code regressions (honestly categorized) · 5c. One product decision for Ian (cosmetic, non-blocking) · 6. Post-deploy smoke checks (prod)

(Deep source: `file:PRODUCTION_DEPLOY_RUNBOOK.md` — retrieve this TOC to know WHICH section to read.)
