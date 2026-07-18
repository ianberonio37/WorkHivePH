---
name: doc-ROLLBACK_RUNBOOK
type: doc
source: file:ROLLBACK_RUNBOOK.md
source_sha: 64d548696fb61758
last_verified: 2026-07-13
supersedes: null
---
## doc · ROLLBACK_RUNBOOK

**Status:** v1.0 (2026-05-27)

**Sections:** Rollback Runbook · 1. Decision tree · 2. Pre-flight (do BEFORE any deploy) · 3. Fast Path (customer-visible issue, ≤ 10 min RTO) · Step 1 — confirm the regression scope (≤ 2 min) · Is it ALL surfaces or one fn? · Step 3A — frontend / static regression · Netlify dashboard → Deploys → click last green deploy → "Publish deploy" · OR via CLI if you have access: · Step 3B — single edge fn regression · Redeploy the previous version from git history: · Step 3C — infrastructure regression (Supabase region issue) · 4. Standard Rollback (regression vs last known good, ≤ 30 min) · Step 1 — verify last-known-good · Pick the most recent commit BEFORE the regression-introducing one. · Step 2 — create a rollback branch · OR for a single commit: · Step 3 — run the pre-deploy gate on the rollback · All checks must PASS. If they don't, abort rollback — investigate. · Step 4 — deploy · Frontend · Then merge via PR or fast-forward to master. · Edge functions · Step 5 — verify recovery · Loop until every /health is 200: · Step 6 — post-mortem within 24h · 5. Database rollback (PITR — Point-In-Time Recovery) · Steps · 5b. Restore from a logical dump (Arc S — when PITR is unavailable / expired) · Take a dump (also run on a schedule in prod)

(Deep source: `file:ROLLBACK_RUNBOOK.md` — retrieve this TOC to know WHICH section to read.)
