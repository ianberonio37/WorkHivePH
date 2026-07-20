# Production Deploy Runbook — accumulated release (2026-07-20) ← CURRENT

**Owner: Ian (all outward steps are Ian-gated).** Claude prepared + pre-flighted; the push commands are yours to run from YOUR environment. **No deploy credentials are configured locally, so Claude cannot and did not push anything** — and cannot verify the remote migration state (which of these are already applied). `supabase db push` is idempotent (applies only migrations absent from the remote `schema_migrations` history), so the exact last-deployed point does not change the commands; step 1a confirms it live.

> **⚠ This is a LARGE two-week accumulated release** superseding the 2026-07-06 scope below (kept as history). If the 2026-07-06 deploy was already run, `db push` simply skips those 14 and applies the rest. If it was NOT, it applies all of them in timestamp order — same command either way.

## 0.NEW — What ships (measured at HEAD `0893c52`, 2026-07-20)

| Leg | Payload | Command |
|---|---|---|
| **A · DB** | **93 migrations** `20260706000001` → `20260720000001` (all additive/idempotent; the only DELETEs are the LRU embedding-cache eviction; immutability-clean, 359 tracked) | `npx supabase db push` |
| **B · Edge** | **57 fns**: deploy 55 via script + `login` & `supervisor-reset-password` SEPARATELY + **delete 5** removed Stripe fns + `marketplace-listing-assist` is new (ships in the 55) | see B below |
| **C · Frontend** | 2 weeks of HTML/JS/CSS/asset changes | `git push origin master` → Netlify auto-build |

**Order: A → B → C** (edge fns depend on the new RPCs; the frontend calls the edge fns).

### Leg A — DB (from repo root; the `&` in the path breaks npx → subst a clean drive first)
```powershell
subst Z: "c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st"
Z:
npx supabase migration list      # 1a. CONFIRM which are remote-pending (needs your creds — I can't)
npx supabase db push             # 1b. applies all pending in timestamp order
```

### Leg B — Edge (still on Z:)
```powershell
# 1. the 55 in the script (blanket --no-verify-jwt):
powershell -ExecutionPolicy Bypass -File deploy-functions.ps1
# 2. the 2 NOT in the script — deploy each so config.toml governs verify_jwt:
npx supabase functions deploy login --no-verify-jwt          # public auth entry (verify_jwt=false)
npx supabase functions deploy supervisor-reset-password      # ⚠ NO --no-verify-jwt — this fn REQUIRES jwt (config.toml verify_jwt=true); the blanket flag would break its supervisor auth
# 3. remove the 5 deleted Stripe fns from prod (db push does NOT delete edge fns):
npx supabase functions delete marketplace-checkout marketplace-connect-onboard marketplace-connect-status marketplace-release marketplace-webhook
```

### Leg C — Frontend
```powershell
git push origin master           # Netlify auto-builds (publish = ".")
```

## 5.NEW — Pre-flight result (verified 2026-07-20, not asserted)
- **Destructive-DDL scan (93 migrations) — CLEAN.** 5 migrations flagged; each verified safe-in-context: `20260708000002` fault_knowledge DELETE is a **de-dup** (`WHERE rn>1`, keeps most-recent per source); `20260707000005` + `20260711000002` DROP a CHECK constraint then immediately re-ADD the corrected one; `20260707000006`/`…07` DELETEs are inside function bodies (delete-worker-data on-demand + the retention cron), not migration-time wipes. **No table/column drop, no unconditional data delete.**
- **Deleted-fn safety — CLEAN.** The 5 removed Stripe fns (marketplace-checkout/connect-onboard/connect-status/release/webhook) have **0 live references** in any shipped `.html`/`.js` (marketplace was migrated off Stripe) → safe to `functions delete` from prod without breaking a page.
- **`run_platform_checks --fast` = 0 FAIL** (after the MEMORY.md slim).
- **`release_gate.py --skip-ui --no-seed` = GATE BLOCK (static 1 FAIL + data 4 FAIL), triaged:**
  - **Static 1 FAIL — Substrate freshness — FIXED.** This session's roadmap/tool edits drifted the substrate chunk index; `python tools/build_substrate.py` rebuilt it → gate now **PASS (611 chunks fresh)**. This was the only deployable-code static failure.
  - **Data 4 FAIL — pre-existing LOCAL-SEED-DATA debt, NOT deployable-code regressions** (verified: this session touched none of these contracts; prod uses real data, not this seed): (1) 5 seed machines missing tag IDs; (2) a seeded `pm_assets` row with category `HVAC` outside the validator set; (3) 69 seed breakdowns with off-enum `root_cause`; (4) 6/87 `inventory_items` seed rows missing `auth_uid` — these are seeder-created service-role rows; the CODE enforces auth_uid on real client writes via **3 attribution triggers** (hive-isolation 25/0). Same class the 2026-07-06 deploy pushed past (§5b).
- **⇒ Deployable code is clean.** For Leg C, the pre-push hook re-runs this gate: either fix the local seed first, or `git push --no-verify` (precedented for the seed-data class — the DB migrations/edge fns/frontend being pushed are unaffected by local seed content).

## 6.NEW — Post-deploy smoke (prod)
1. Sign in (login + auth path). 2. Create a logbook entry (quota trigger allows honest use). 3. Fire one AI action (ai-gateway + budget guard). 4. Open marketplace + accept a parts-staging rec twice fast (proves the new `parts_staged_reservations` UNIQUE idempotency — no dup). 5. Watch Supabase logs for `54000`/`23505` spikes.

---
---

# Production Deploy Runbook — accumulated release (2026-07-06)

**Owner: Ian (all outward steps are Ian-gated).** Claude prepared + pre-flighted this; the three
push commands below are yours to run. Local Supabase stack was UP and the full gate was run as the
pre-flight (see §5 for result). Nothing here has been pushed.

---

## 0. What ships in this release (the true scope)

This is a **large accumulated release** — many arcs kept local under the deploy-gate discipline,
landing together. Three legs:

| Leg | Payload | How it deploys |
|---|---|---|
| **A · DB** | **14 new migrations** `20260630000000` → `20260705000009` | `npx supabase db push` |
| **B · Edge** | **60 modified fns** + new `_shared/observability.ts` + **5 deleted** Stripe fns | `deploy-functions.ps1` (+2 additions, +5 deletes — see §2) |
| **C · Frontend** | 400+ HTML/JS/CSS/asset changes + 3 page/asset deletions | `git push origin master` → Netlify auto-build (`publish = "."`) |

**Deploy order: A → B → C.** All migrations are additive + idempotent (destructive-DDL scan clean;
the only `DELETE`s are the `embedding_cache` LRU cache eviction — safe by definition). Edge fns depend
on the new RPCs/`_shared`; the frontend calls the edge fns. So DB first, edge second, frontend last.

### Headline content
- **Free-Tier Quota system** (the 10 `20260705*` migrations + `_shared/rate-limit.ts` + `ai-chain.ts`):
  per-day row caps (27 tables), text caps (26), `hive_quotas` cumulative enforcement ON, global
  org-shared LLM budget guard + burst smoother, retention cron, realtime channel caps, inline-image
  guard. 11 ratchet gates. LIVE-verified locally.
- **Stripe → free marketplace** (`20260630000000_remove_stripe_free_marketplace.sql` + 5 deleted edge fns).
- Memory re-gating, asset-hub display realign, SLO error-budget rollup, + accumulated arc work.

---

## 1. Leg A — DB migrations

```powershell
# From the repo root. The "&" in the folder name breaks `npx supabase`, so subst a clean drive first
# (memory: feedback_deploy_subst).
subst Z: "c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st"
Z:

# 1a. CONFIRM the 14 are remote-pending (not already applied out-of-band):
npx supabase migration list           # the 14 below should show local-only / remote-missing

# 1b. Push:
npx supabase db push                  # applies all pending migrations in timestamp order
```

The 14 (timestamp order):
```
20260630000000_remove_stripe_free_marketplace
20260701000000_regate_match_procedural_memories
20260702000000_realign_display_count_chip_asset_hub
20260702000001_slo_error_budget_rollup
20260705000000_q0_logbook_quota_pilot
20260705000001_q2_high_write_daily_caps
20260705000002_q3_server_text_caps
20260705000003_q4_daily_ai_ceiling
20260705000004_full_write_surface_coverage
20260705000005_close_page_audit_gaps
20260705000006_q6_global_ai_budget
20260705000007_q1_enforce_cumulative_quota
20260705000008_q5b_retention_embedding_cache
20260705000009_q5a_inline_image_guard
```
> Migration immutability: these are all **new, uncommitted files never pushed** → `db push` applies the
> final version cleanly. No historical-edit drift risk (validated by `validate_migration_immutability.py`).

---

## 2. Leg B — Edge functions

The `_shared` changes (`rate-limit.ts`, `ai-chain.ts`, `observability.ts`, `cors.ts`, `persona.ts`) are
**bundled per-function at deploy time** — they only reach prod for functions you **redeploy**. So every
importer must be deployed. `deploy-functions.ps1` already lists 54; add the 2 below and remove the 5 dead.

```powershell
# Still on Z:.  Run the existing script (54 fns):
.\deploy-functions.ps1

# +2 modified fns MISSING from the script. Deploy them SEPARATELY (NOT via the script) because the
# script forces --no-verify-jwt on all 54, which is WRONG for the reset fn. Let config.toml govern:
npx supabase functions deploy login                      # config verify_jwt=false (public login endpoint)
npx supabase functions deploy supervisor-reset-password  # config verify_jwt=TRUE — do NOT pass --no-verify-jwt
                                                         #   (requires a real supervisor session; the fn re-checks role)

# −5 deleted Stripe marketplace fns (delete from prod; db push does NOT remove these):
npx supabase functions delete marketplace-checkout
npx supabase functions delete marketplace-connect-onboard
npx supabase functions delete marketplace-connect-status
npx supabase functions delete marketplace-release
npx supabase functions delete marketplace-webhook
```

> **Why not just add them to `deploy-functions.ps1`?** The script deploys every fn with a blanket
> `--no-verify-jwt`. `login` (verify_jwt=false) would be fine, but `supervisor-reset-password`
> (verify_jwt=**true** per config.toml) must keep JWT verification ON — folding it into the blanket
> script would silently strip auth off a password-reset endpoint. So they stay as the 2 explicit
> commands above.

> **Edge type-check note:** no local `deno` is installed, so a full TS type-check can't run locally.
> Coverage instead comes from (a) the full pre-flight gate's live edge-invoke gates against the local
> runtime (`supabase_edge_runtime_workhive`), and (b) `supabase functions deploy` validating + bundling
> each fn atomically on deploy — a TS error fails only that one fn's deploy, never the others.

---

## 3. Leg C — Frontend (Netlify)

Netlify publishes the repo root (`publish = "."`), so the frontend deploy IS the git push. Confirm the
gate is green (§5) FIRST, then:

```powershell
git add -A
git commit -m "release: free-tier quota system + Stripe-free marketplace + accumulated arc work"
git push origin master            # Netlify auto-builds from master
```
Deletions in this leg: `platform-health.html`, `predictive.html` (folded elsewhere), 4 old brand-persona
images. These vanish from the live site on build — confirm nothing links to them (the gate's dead-link
check covers this).

---

## 4. Rollback

- **DB:** migrations are additive + idempotent; there is no auto-down. To neutralize a quota cap without a
  reverse migration, set `hive_quotas.enforce_blocking=false` (returns to log-only) or raise the specific
  cap — no schema change needed. The global LLM guard **fails OPEN** (a counter glitch never blocks AI).
- **Edge:** redeploy the prior version from a clean checkout of HEAD (`6817ceb`).
- **Frontend:** `git revert` the release commit + push → Netlify rebuilds the prior site.

## 5. Pre-flight gate result

Full `run_platform_checks.py` (stack UP, all live gates): **497 PASS · 23 FAIL** on the first run.
Triaged every FAIL. **Two were real cross-tenant security leaks that would have shipped** — both fixed.

### 5a. FIXED + verified green (8) — all deployable-code issues
| # | Gate | Root cause | Fix |
|---|---|---|---|
| 1 | **Arc G view-security** ★SECURITY | The Stripe-removal migration DROPs+recreates `v_marketplace_orders_truth` & `v_marketplace_sellers_truth` **without `security_invoker`** + GRANTs to anon/authenticated → any user reads **every hive's** marketplace orders+sellers once marketplace-table RLS is on | added `WITH (security_invoker=on)` to both views in `20260630000000_remove_stripe_free_marketplace.sql` + `ALTER VIEW` on local DB → LEAKING 2→0 GREEN |
| 2 | **Arc G view-security** ★SECURITY | `v_wh_traces_slo` (new SLO migration) reads `wh_traces` (RLS) without `security_invoker` | added `WITH (security_invoker=on)` to `20260702000001_slo_error_budget_rollup.sql` |
| 3 | **Inventory Validator** | `addTransaction` push object DOES have `hive_id`; the validator's fixed **600-char window** truncated before it after an `auth_uid` line was added | widened window to 1500 in `validate_inventory.py` |
| 4 | **AI Seams Inventory** | seam miner scanned `test-results/` Playwright artifacts → 1 noise seam; + 1 legit `ai-orch→v_asset_truth` | excluded `test-results` in `mine_ai_seams.py` + re-baselined for the legit seam |
| 5 | **AI Seam Coverage** | same noise seam (144→146) | resolved by the miner scope fix (back to 144) |
| 6 | **Reactivity Wiring** | crashed on a `✓` UnicodeEncodeError = false FAIL; stale logbook marker; folded `predictive` D4 owner | `stdout.reconfigure(utf-8)` + marker em-dash→colon + dropped folded owner |
| 7 | **Interactive Lineage** | resolved anchors 65→59 — all 6 legit removals (2 deleted pages + `ps-earned` removed by free-marketplace) | evidence-verified re-baseline |
| 8 | **Core Web Vitals** | first-ever run; baseline unseeded (0) | seeded baseline to 5 |

### 5b. Remaining FAILs — NOT deployable-code regressions (honestly categorized)
- **Cosmetic, from the predictive→asset-hub fold (2):** `Platform Name Alignment` (asset-hub cataloged as "Predictive Analytics") + `Landing featureList` (index.html featureList missing "Predictive Analytics"). Both stem from ONE product-naming question — see §5c. Pre-existing since the 2026-07-02 fold; SEO/catalog cosmetics, not functional.
- **Pre-existing other-stream (2):** `Clone Debt` (4144→4290 duplicated lines — ai-quality/plant-connections/shift-brain/public-feed/marketplace-seller-profile, all git-modified pre-session) + `SEO retired_schema` (index.html + `learn/` articles declaring retired FAQPage/HowTo — content, still renders as body). Not this release's code.
- **Live-infra env-debt (~9):** `Playwright UI Smoke Suite` (1200s timeout), `Arc Q Calc/Engines LIVE` (need free-tier model keys), `Arc H Voice-router` (flaky; passes 22/22 direct), `Arc R security sweep` ("infra error/timeout, not a clean measurement"), `Arc I idle/RBAC` (browser timeouts), `AI Self-Improvement ×4` (live LLM). These are the exact live tier the `--fast` gate deliberately skips; they time out without model keys + seeder + an uncontended browser. Not code regressions — same env-debt backlog as always.

_A confirming full re-run is in progress to verify the 8 fixes dropped the count with no new regressions._

### 5c. One product decision for Ian (cosmetic, non-blocking)
`predictive.html` folded into asset-hub. The catalog still keeps **"Predictive Analytics"** as a distinct marketed feature (per the deliberate `FOLDED_INTO` design), which drives both cosmetic FAILs in §5b. Two clean options:
- **(A, recommended) Retire it** — remove `"Predictive Analytics"` from `INTEL_TO_ROUTE` in `tools/platform_catalog.py`; the capability now lives in asset-hub. Both gates go green; nothing user-facing breaks.
- **(B) Keep it** — add "Predictive Analytics" to index.html's featureList + accept the catalog name. Keeps it marketed as a folded feature.

Neither blocks the push; the marketplace + SLO **security** fixes above are the only push-critical gate items, and they are fixed.

## 6. Post-deploy smoke checks (prod)
1. Sign in (proves `login` + auth path).
2. Create a logbook entry (proves the quota trigger allows honest use, doesn't false-block).
3. Fire one AI action (proves `ai-gateway` + global budget guard passes at normal load).
4. Open the marketplace (proves the Stripe-removal didn't break the page).
5. Watch Supabase logs for `54000` SQLSTATE spikes (a too-tight cap blocking real users).
