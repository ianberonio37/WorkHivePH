# Rollback Runbook

**Status:** v1.0 (2026-05-27)
**Owner:** Ian + Claude
**Closes:** (H, GH) cell from `COMPREHENSIVE_STUDY_FULLSTACK_GATE.md` §4
**Test cadence:** quarterly game day (see `RTO_RPO_DECLARATION.md` §C)

Production rollbacks must be **boring** — predictable, scriptable, and tested. Without a documented runbook, rollback becomes "git revert + redeploy + pray," and the actual MTTR is whatever it takes you to remember the steps under stress.

---

## 1. Decision tree

```
Is the issue customer-visible right now?
  └─ YES → §3 Fast Path (≤ 10 min)
  └─ NO  → Is it a regression vs last known good?
              └─ YES → §4 Standard Rollback (≤ 30 min)
              └─ NO  → §5 Investigate first; rollback only if needed
```

Default to fast path when in doubt. A reverted deploy is recoverable; angry customers are not.

---

## 2. Pre-flight (do BEFORE any deploy)

Every prod deploy must satisfy these gates. If any of these are not green, do not deploy:

1. **`python tools/pre_deploy_gate.py`** — runs Layer 0 fast + sentinel + Layer 2 Tier 1 + git-clean.
2. **`git log --oneline -1`** — note the SHA you're deploying. Save it.
3. **Snapshot the last-known-good edge fn versions:**
   ```bash
   supabase functions list --output json > .tmp/edge_fns_pre_deploy_$(date +%Y%m%d_%H%M).json
   ```
4. **Snapshot platform_health.json:**
   ```bash
   cp platform_health.json .tmp/platform_health_pre_deploy_$(date +%Y%m%d_%H%M).json
   ```

---

## 3. Fast Path (customer-visible issue, ≤ 10 min RTO)

### Step 1 — confirm the regression scope (≤ 2 min)
```bash
# Is it ALL surfaces or one fn?
curl -fsS https://<project>.supabase.co/functions/v1/ai-gateway/health | jq .
curl -fsS https://<project>.supabase.co/functions/v1/agentic-rag-loop/health | jq .
```

- **All /health endpoints 200 + customer reports error** → frontend/static regression → §3A
- **One /health 503** → edge fn regression → §3B
- **Multiple /health 503** → infrastructure regression → §3C

### Step 3A — frontend / static regression
```bash
# Netlify dashboard → Deploys → click last green deploy → "Publish deploy"
# OR via CLI if you have access:
netlify deploy:list --json | jq '.[1].id' | xargs -I{} netlify deploy:publish {}
```
Customer impact ends as soon as the CDN propagates (~30-60 sec).

### Step 3B — single edge fn regression
```bash
# Redeploy the previous version from git history:
git checkout <last-known-good-sha> -- supabase/functions/<fn-name>/
.\deploy-functions.ps1 -Function <fn-name>
git checkout HEAD -- supabase/functions/<fn-name>/  # restore working tree
```

### Step 3C — infrastructure regression (Supabase region issue)
1. Check https://status.supabase.com — if Supabase reports the issue, no action; wait + comms.
2. If Supabase is green and we're red, escalate via Supabase support with `project_ref` + 5 most recent edge fn invocation IDs.
3. If RTO threshold exceeded, fail over to read-only mode by toggling `wh_feature_flags.read_only=true` (P2 — not yet implemented).

---

## 4. Standard Rollback (regression vs last known good, ≤ 30 min)

### Step 1 — verify last-known-good
```bash
git log --oneline -10
# Pick the most recent commit BEFORE the regression-introducing one.
LAST_GOOD=<sha>
```

### Step 2 — create a rollback branch
```bash
git checkout -b rollback-to-$LAST_GOOD master
git revert --no-edit <bad-sha>..HEAD   # revert every commit since last_good
# OR for a single commit:
git revert --no-edit <bad-sha>
```

### Step 3 — run the pre-deploy gate on the rollback
```bash
python tools/pre_deploy_gate.py
# All checks must PASS. If they don't, abort rollback — investigate.
```

### Step 4 — deploy
```bash
# Frontend
git push origin rollback-to-$LAST_GOOD
# Then merge via PR or fast-forward to master.

# Edge functions
.\deploy-functions.ps1   # deploys all that changed
```

### Step 5 — verify recovery
```bash
# Loop until every /health is 200:
for fn in ai-gateway agentic-rag-loop analytics-orchestrator engineering-calc-agent; do
  curl -fsS https://<project>.supabase.co/functions/v1/$fn/health | jq -r '.ok' || echo "FAIL: $fn"
done
```

### Step 6 — post-mortem within 24h
- What broke?
- Why didn't the pre-deploy gate catch it?
- Add a validator that WOULD have caught it (run `/harden`).
- Add a regression-pin to `tests/journey-regression-pins.spec.ts`.

---

## 5. Database rollback (PITR — Point-In-Time Recovery)

**Use only when migration / data corruption is the cause.** Database rollback is slower than code rollback and harder to undo. Confirm with at least one teammate.

### Steps
1. **Identify the target timestamp** — the moment just before the bad migration ran. From `platform_health.json` snapshots in `.tmp/` you can usually narrow to ±2 minutes.
2. **Notify customers** if PITR will exceed 5 minutes. Status page if available.
3. **Run PITR via Supabase dashboard:** Project → Database → Backups → Point-in-time recovery → enter target timestamp.
4. **Re-apply any post-PITR migrations** that were correct (i.e. the schema changes you want to keep). Likely none if rolling back a single bad migration.
5. **Verify with `validate_schema.py`** that the live DB matches the migration history.
6. **Re-seed test data if local development was using prod:** `python test-data-seeder/seed.py reset && seed.py seed`.

---

## 5b. Restore from a logical dump (Arc S — when PITR is unavailable / expired)

**Use when** the PITR window (7 days) has expired, PITR is unavailable (region/account issue), or you
need a single-table restore without rolling the whole DB back. The logical dump is the
operator-controlled backup that complements managed PITR (RTO_RPO_DECLARATION.md).

### Take a dump (also run on a schedule in prod)
```bash
python tools/data_backup.py --backup     # -> backups/wh_data_<ts>.sql + manifest.json (per-table row counts)
```

### Prove a dump restores (the drill — run it; don't trust an untested backup)
```bash
python tools/data_backup.py --drill      # dumps a critical table, restores it into a scratch schema,
                                          # asserts restored rowcount == source, reports elapsed (RTO), cleans up
```

### Restore from a dump file (recovery)
1. **Identify the dump** in `backups/` and its `manifest.json` (the row counts you expect back).
2. **Restore into the live DB** (data-only — the schema must already exist from migrations):
   ```bash
   docker exec -i supabase_db_workhive psql -U postgres -d postgres -v ON_ERROR_STOP=1 < backups/wh_data_<ts>.sql
   ```
   For a SINGLE table, extract its `COPY public.<table> ... \.` block from the dump and restore just that block.
3. **Idempotency:** the dump is `--data-only`; if rows still exist, `TRUNCATE public.<table>` first (or restore
   into a scratch schema and `INSERT ... ON CONFLICT DO NOTHING` the gaps) to avoid PK collisions.
4. **Verify row counts** against the manifest, then run `validate_schema.py` + `python tools/dataloss_monitor.py`.

### Catch a silent loss early (so PITR/dump can still recover it)
```bash
python tools/dataloss_monitor.py --snapshot   # schedule this; the next run alerts on a >20% drop per critical table
```

---

## 6. Edge fn version pinning (operational)

Supabase doesn't currently expose versioned aliases via CLI. The closest we have:

```bash
# List recent deploys of a fn (look at versions in the dashboard):
supabase functions list

# To "pin" a known-good version, capture its source SHA:
git rev-parse HEAD:supabase/functions/<fn>/index.ts > .tmp/<fn>_known_good.sha
```

When rolling back, restore from that SHA:
```bash
git show <sha>:supabase/functions/<fn>/index.ts > supabase/functions/<fn>/index.ts.tmp
mv supabase/functions/<fn>/index.ts.tmp supabase/functions/<fn>/index.ts
.\deploy-functions.ps1 -Function <fn>
```

P2 deliverable: blue/green via `--no-verify-jwt + alias` (see `COMPREHENSIVE_STUDY_FULLSTACK_GATE.md` §7 item 14).

---

## 7. Game day (quarterly test)

The runbook is theatre until practised. Once per quarter, **schedule a game day** to test ONE scenario end-to-end:

| Quarter | Scenario | Target RTO |
|---|---|---|
| Q3 2026 | Single edge fn 5xx (ai-gateway) | 10 min |
| Q4 2026 | Bad migration shipped to prod | 30 min |
| Q1 2027 | Supabase region outage simulation | 1 hour |
| Q2 2027 | Cross-hive data leak detected | 4 hours |

Each game day produces:
- Actual RTO achieved (vs target)
- Pain points discovered
- Runbook patches (this file gets updated)
- One new validator added via `/harden`

---

## 8. Cross-links

- [PLATFORM_ROADMAP.md](PLATFORM_ROADMAP.md) — operational tracker
- [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md) — architectural foundation
- [RTO_RPO_DECLARATION.md](RTO_RPO_DECLARATION.md) — recovery targets per data class
- [CAPACITY_PLAN.md](CAPACITY_PLAN.md) — current ceilings + investment triggers
- [tools/pre_deploy_gate.py](tools/pre_deploy_gate.py) — the gate every deploy must pass

---

## 9. The standing rule

**Never deploy on a Friday afternoon.** If you must, the on-call window extends to Sunday end-of-day. Document the exception in the commit message.
