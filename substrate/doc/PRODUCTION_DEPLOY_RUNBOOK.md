---
name: doc-PRODUCTION_DEPLOY_RUNBOOK
type: doc
source: file:PRODUCTION_DEPLOY_RUNBOOK.md
source_sha: d565532637e8c413
last_verified: 2026-07-13
supersedes: null
---
## doc · PRODUCTION_DEPLOY_RUNBOOK

> **✅ DEPLOYED 2026-07-20 (executed by Claude with Ian's live authorization "you have everything I have go push everything needed for production").** The remote was current through `20260718000004` (p

**Sections:** Production Deploy Runbook — accumulated release (2026-07-20) ← CURRENT · 0.NEW — What ships (measured at HEAD `0893c52`, 2026-07-20) · Leg A — DB (from repo root; the `&` in the path breaks npx → subst a clean drive first) · Leg B — Edge (still on Z:) · 1. the 55 in the script (blanket --no-verify-jwt): · 2. the 2 NOT in the script — deploy each so config.toml governs verify_jwt: · 3. remove the 5 deleted Stripe fns from prod (db push does NOT delete edge fns): · Leg C — Frontend · 5.NEW — Pre-flight result (verified 2026-07-20, not asserted) · 6.NEW — Post-deploy smoke (prod) · Production Deploy Runbook — accumulated release (2026-07-06) · 0. What ships in this release (the true scope) · Headline content · 1. Leg A — DB migrations · From the repo root. The "&" in the folder name breaks `npx supabase`, so subst a clean drive first · (memory: feedback_deploy_subst). · 1a. CONFIRM the 14 are remote-pending (not already applied out-of-band): · 1b. Push: · 2. Leg B — Edge functions · Still on Z:.  Run the existing script (54 fns): · +2 modified fns MISSING from the script. Deploy them SEPARATELY (NOT via the script) because the · script forces --no-verify-jwt on all 54, which is WRONG for the reset fn. Let config.toml govern: · −5 deleted Stripe marketplace fns (delete from prod; db push does NOT remove these): · 3. Leg C — Frontend (Netlify) · 4. Rollback · 5. Pre-flight gate result · 5a. FIXED + verified green (8) — all deployable-code issues · 5b. Remaining FAILs — NOT deployable-code regressions (honestly categorized) · 5c. One product decision for Ian (cosmetic, non-blocking) · 6. Post-deploy smoke checks (prod)

(Deep source: `file:PRODUCTION_DEPLOY_RUNBOOK.md` — retrieve this TOC to know WHICH section to read.)
