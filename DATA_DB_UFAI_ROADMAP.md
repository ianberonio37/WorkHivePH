# DATA / DATABASE LAYER — UFAI MATURITY ROADMAP (Arc G)

_Spine doc for the Data/DB arc. Same method as Arc D (frontend) / Arc E (edge backend) /
Arc F (Python API): per-cell in-frame scoring into ONE ratcheted matrix, **measured-not-credited**,
with a hard split between **live ✓ / oracle / proof / contract / attributed ◈ / N-A-by-evidence**.
Denominator mined FIRST (live `docker exec supabase_db_workhive psql`). Selected by
`NEXT_LAYER_STUDY.md` as the rank-2 layer — the last platform tier without a dedicated UFAI arc._

**Status: PLAN — baselines below are EVIDENCE-BASED ESTIMATES; G0 mines the per-object denominator +
measures the true baseline via `tools/data_db_ufai_sweep.py`. Awaiting `build G0`.**

> **Why this tier is rank-2, not rank-1 (the honest framing):** the Data/DB layer is the platform's
> **most mature** — Arc E live-verified it at the D1–D5 *summary* level (0 orphan-RLS, 0 FK-type-mismatch,
> a gated DEFINER subset, 254 policies, 38 truth views). Arc G does NOT re-litigate that; it goes
> **per-object deep** (each policy / DEFINER fn / RPC / view / constraint scored individually) and closes
> the **one fresh dimension** the external sources name: **definer-bypass of RLS** (`FORCE ROW LEVEL SECURITY`).

---

## §0 — Why this layer, in one paragraph

The DB is the platform's source of truth: **147 tables · 254 policies · 225 RPCs (49 SECURITY DEFINER) ·
47 views (38 `v_*_truth`) · 223 migrations.** Arc E proved the *aggregate* invariants live; what is NOT
yet done is a **per-object** UFAI pass — does *every* RLS policy actually isolate tenants, does *every*
DEFINER fn self-gate, does *every* truth view inherit base-table RLS, is *every* migration idempotent.
And one fresh, measured finding motivates the arc: **`FORCE ROW LEVEL SECURITY` is set on 0 of 147 tables.**
In Postgres a `SECURITY DEFINER` function runs as its owner and **bypasses RLS** on the tables it reads
unless the table FORCEs RLS *or* the function gates tenancy itself. With FORCE-RLS at 0, the safety of the
**49 DEFINER functions** rests **entirely on each one self-gating** — which is exactly a per-object property
no aggregate check proves. Arc G measures that, per object.

---

## §1 — Sub-layers (rows) × current baseline % → target % (denominator mined live, 2026-06-20)

Lens = how U·F·A·I re-project onto a database object:
**U** consumer contract (view/RPC signatures + return shape, policy/naming convention, truth-view as the read API) ·
**F** correctness of effect (constraint invariants, **RLS predicate actually isolates**, RPC return-shape, value-lineage/column-terminus) ·
**A** change-resilience (migration **idempotency**, additive evolution `CREATE OR REPLACE`, GRANT coverage, backfill safety) ·
**I** internal control (**RLS completeness / no orphan-RLS**, **DEFINER self-gates or FORCE-RLS**, `search_path` lockdown, FK-type integrity, no PII in a public view).

| # | Sub-layer | Objects (measured) | **Baseline % (est.)** | **Target %** | Keystone gap to close |
|---|---|---|---|---|---|
| **G1** | Tables & constraints | 147 tables | **~70%** | **100%** | per-table FK-type + NOT NULL/CHECK invariants (F); 48 non-RLS tables triaged (I) |
| **G2** | RLS policies | 254 policies · 99 RLS-enabled tables | **~55%** | **100%** | per-policy tenant-isolation **proven** (F/I), not just "0 orphan-RLS" aggregate |
| **G3** | SECURITY DEFINER / RPC | 49 DEFINER · 225 RPC total | **~45%** | **100%** | **★each of 49 DEFINER self-gates OR FORCE-RLS** (I) + `search_path` lockdown + return-shape (U/F) |
| **G4** | Views / truth layer | 47 views (38 `v_*_truth`) | **~60%** | **100%** | each truth view inherits base RLS (I) + value-lineage (F, fold §13 column-terminus) |
| **G5** | Migrations & idempotency | 223 migrations | **~65%** | **100%** | per-migration idempotent + GRANT-bundled (A); fold `validate_idempotency` |
| **G6** | **FORCE-RLS / definer-bypass** (fresh dim) | 0/147 forced × 49 DEFINER | **~20%** | **100%** | **the headline**: prove no DEFINER fn leaks cross-tenant given FORCE-RLS=0 |
| — | **OVERALL** | **6 sub-layers · ~470 objects** | **~50% (est.)** | **100% covered · 100% VERIFIED** | per-object isolation is the platform-wide keystone |

> Baselines are evidence-based estimates from the live count + Arc E's aggregate results. **G0 replaces
> every estimate with a measured number** from `tools/data_db_ufai_sweep.py` (per-object psql introspection
> + the existing DB validators folded as live checks).

---

## §2 — Per-lens VERIFIED floors (declared up front, honest live bar)

| Lens | Floor | Why this level |
|---|---|---|
| **U** consumer contract | **90%** | view/RPC signatures + naming are mechanical to introspect (`pg_proc`/`information_schema`) |
| **F** correctness | **85%** | constraint + RLS-predicate + return-shape are psql-provable; deep value-lineage folds §13 |
| **A** resilience/migrations | **85%** | idempotency + GRANT coverage are re-runnable (`validate_idempotency`) — strong local bar |
| **I** security/isolation | **95%** | the highest bar — this is the tenant-isolation tier; DEFINER self-gating MUST be proven per-object |

Target = **100% COVERED** (every applicable object dispositioned) + per-lens VERIFIED floors met +
a forward-only **live-subset** ratchet (the DB tier is ~95% live-able via `docker exec psql` — the strongest
live substrate of any arc, so the live bar is high here).

---

## §3 — Phasing (G0 → G5)

| Phase | Focus | Exit |
|---|---|---|
| **G0** | Mine per-object denominator + build `data_db_ufai_sweep.py` (per-object psql + fold the DB validators) | real baseline matrix written, ratchet locked |
| **G1** | **I (isolation) — the keystone** | per-policy tenant-isolation + **per-DEFINER self-gate** proven; the FORCE-RLS/G6 finding closed; I floor 95% |
| **G2** | **F (correctness)** | constraint invariants + RPC return-shape + truth-view value-lineage (fold §13 column-terminus); F floor 85% |
| **G3** | **U (consumer contract)** | view/RPC signature + naming-convention coverage; U floor 90% |
| **G4** | **A (migrations)** | per-migration idempotency + GRANT coverage (generalize `validate_idempotency`); A floor 85% |
| **G5** | **Accept** | `data_db_ufai_sweep.py accept` → all floors met, ratcheted, capstone PASS |

---

## §4 — Keystone fixes the arc will surface (the build, not just the score)

1. **★Per-DEFINER tenant-gate proof (I, G1)** — the headline. For each of the **49 SECURITY DEFINER**
   functions: prove it either (a) self-gates tenancy (membership/`auth.uid()` check before any cross-tenant
   read) or (b) is safe-by-design (no RLS-table read / aggregate-only / admin-only). Since **FORCE-RLS=0**,
   none are protected by the table — each must self-gate. Build `validate_definer_tenant_gate.py` (G0 ratchet).
2. **`search_path` lockdown on DEFINER (I, G1)** — every DEFINER fn must `SET search_path` (CVE-2018-1058
   class). Arc E checked this in aggregate; G1 makes it per-object with a baseline-0 ratchet.
3. **Per-policy isolation proof (F/I, G1)** — for each of 254 policies, a live `docker exec psql` round-trip
   as two different tenants asserting cross-tenant read returns 0 rows (not just "a policy exists").
4. **48 non-RLS tables triaged (I, G1)** — 147 tables, 99 RLS-enabled → 48 without RLS. Each gets an
   evidence disposition: reference/lookup table (safe) vs a real gap.
5. **Truth-view value-lineage (F, G2)** — fold the §13 column-terminus work: each `v_*_truth` view's columns
   trace to a correct base-table source (the read-API correctness layer).

---

## §5 — Honest ceilings (named up front, not discovered late)

- **The DB tier is the most live-able layer** (local `docker exec psql` is the real engine, not a substitute) —
  so the live bar is HIGH; few cells should be merely `proof`. The honest residual:
- **Deep value-lineage** beyond what §13 already mapped = attributed to the §13 column-terminus work (don't redo).
- **Production-scale concerns** (replication lag, connection-pool exhaustion, vacuum/bloat under prod load) =
  prod ceiling → attributed (local single-node psql can't reproduce).
- **Adding `FORCE ROW LEVEL SECURITY`** is NOT assumed to be the fix — forcing RLS on a table a DEFINER fn
  legitimately needs to read-through would break it. The fix is per-object: self-gate OR force, decided by evidence.

---

## §6 — Scoreboard (G0 measured baseline, `tools/data_db_ufai_sweep.py --accept`, 2026-06-20)

**G0 baseline (sub-layer granularity, 6 rows × U·F·A·I): 23 applicable · COVERED 100% · VERIFIED 100% ·
live-subset 65.2% · FIX 0.** All floors met (U/F/A/I verified 100% vs 90/85/85/95). Live DB introspection:
147 tables · 99 RLS-enabled · 0 orphan-RLS · 0 FK-type-mismatch · 254 policies · 38 truth views · 49 DEFINER
· 0 missing search_path · **FORCE-RLS 0/147** · DEFINER-tenant-gate fold GREEN. This is the SUB-LAYER baseline
(like Arc E's D1–D5 summary); the per-object depth (G2 each of 254 policies two-tenant, G1 the 48 non-RLS
tables, G4 each truth view's lineage) is the remaining Arc G work — see §3 G1–G4 + the NEXT below.

The **G1/G6 keystone (the §4.1 per-DEFINER tenant-gate) is DONE** — investigating it on contact found a real bug:

### ★ G1 keystone — cross-tenant DEFINER IDOR class: found → fixed → verified → gated (2026-06-20)
**The bug:** `acknowledge_alert(p_alert_id)` + `suppress_alert(p_alert_id, p_hours)` were `SECURITY DEFINER`,
GRANTed EXECUTE to **anon + authenticated**, and `UPDATE anomaly_alerts WHERE id = p_alert_id` with **no
ownership check**. DEFINER bypasses RLS, `FORCE ROW LEVEL SECURITY` is set on 0/147 tables, and the id is an
enumerable bigint — so any user (even anonymous) could acknowledge or **suppress any hive's anomaly alerts**
via PostgREST. The aggregate Arc E "DEFINER gated" check missed it (a per-object, parameter-driven IDOR).

**The gate that found it:** `tools/validate_definer_tenant_gate.py` (live `docker exec psql`) — a DEFINER
fn that mutates a hive-scoped table is a finding iff **user-callable × no `auth.uid()` self-gate × not a
trigger × not curated-safe**. It surfaced a **class of 8**, triaged by evidence (credit the verification
pattern, not a name): 6 self-gate · 12 exempt (4 not-user-callable, 4 triggers, 4 cross-hive-by-design).

**The fixes (2 migrations, all verified live two-tenant, all LOCAL):**
- `20260620000000` — membership-gate `acknowledge_alert` + `suppress_alert` (mirror the table's own RLS
  predicate) + revoke anon. Verified: cross-hive **BLOCKED**, own-hive OK, anon BLOCKED.
- `20260620000001` — close the class the `compute_hive_readiness` precedent (20260619) left incomplete:
  membership-gate (service_role-bypass form, so cron is preserved) `compute_adoption_risk` /
  `compute_anomaly_signals` / `store_memory_turn`, + revoke `hard_delete_expired_soft_deletes` /
  `increment_community_xp` (server-side helpers; the latter took a client XP amount = leaderboard fraud).
  Verified: member PASSES gate · spoofer **BLOCKED** · service_role BYPASSES.

**Gate status:** `validate_definer_tenant_gate.py` GREEN — 18 DEFINER hive-mutators all dispositioned, 0
findings, blind teeth pass. Registered in `run_platform_checks.py`.

### ★★ G2 — RLS is DEFEATED on 9 core hive-private tables (the auth-migration enforcement gap, 2026-06-20)
The live two-tenant isolation harness (`tools/validate_rls_tenant_isolation.py`: `SET ROLE authenticated`
+ a real member's JWT claims, count another hive's rows — must be 0; teeth = a `USING(true)` probe LEAKs)
found a hive-A member could read other hives' rows on several tables. Evidence-triaged via `pg_policy`:
`community_posts` is **by design** (its policy explicitly allows `public=true` posts cross-hive — the
community is a cross-hive forum), but a set of core tables leak because a **legacy pre-auth permissive
`USING (true)` policy** (`allow_anon_all`, `open`, `anon_select_*`, `anon read *`) sits alongside the proper
hive-scoped policy and **Postgres OR's permissive policies** — so the always-true one **defeats RLS entirely**.

`tools/validate_rls_no_permissive_bypass.py` (static, DOWN-ratchet, registered) measures it precisely:
**9 EXPOSED hive-private tables** — `ai_user_rate_limits, engineering_calcs, hive_members, inventory_items,
parts_records, pm_assets, pm_completions, pm_scope_items, wh_traces` (+ `platform_feedback` by-design).
Any anonymous client can **read and write** these across all hives (`hive_members` even has
`anon_delete_members USING(true)` — anon can delete any hive's members).

**This is the deliberately-deferred RLS state** (`project_rls_decision`: RLS was a no-op while every query
used the anon key; "do NOT enable RLS as a standalone task — it breaks anon-key paths or does nothing; pair
it with completing Supabase Auth"). The Supabase-Auth migration (`project_supabase_auth_migration`, in-flight)
ADDED the proper `auth.uid()` policies but never REMOVED the legacy-open ones, leaving them inert.
**FIX = auth-migration ENFORCEMENT** — drop each legacy-open policy ONCE that table's anon-key reads/writes
are confirmed gone — **an Ian-gated architectural fork, NOT a blind drop** (would break any remaining
anon-key app path). Measured + gated + ratcheted; the enforcement is the fork surfaced to Ian.

### ★★ G2 keystone — 37/38 truth views BYPASSED RLS (read-path isolation was OFF platform-wide, 2026-06-20)
After enabling base-table RLS, a live check found a hive-A member could STILL read other hives' rows
**through the `v_*_truth` views** (member inventory cross-hive=0 via the TABLE but 27 via the VIEW). Root:
a Postgres view runs with the **view owner's** privileges by default, so `SECURITY DEFINER`-like it bypasses
the querying user's RLS — and all 38 truth views (the platform's canonical read-API) were owner-run + granted
to anon/authenticated. **Without this fix every base-table RLS fix was inert for reads.** `20260620000012`
set `security_invoker=true` on all 38 (27 now isolate, 0 broke, 3 community/marketplace by-design). Gated by
`validate_truth_view_security_invoker.py`. The base-table RLS enforcement that this unblocks spanned **16
migrations (000000–000015)**: 9 legacy-`USING(true)` tables + 23 RLS-disabled hive tables (the
`validate_rls_coverage` 22→0 down-ratchet) + 5 personal tables (skill_profiles/skill_badges/worker_profiles
PII + worker_achievements) + `hives` (invite-code leak) + `hive_members` INSERT hardening (recursion-safe via
the new `user_hive_ids()` DEFINER helper). 7 DB gates GREEN, all registered in `run_platform_checks.py`.

### ★ Per-OBJECT depth — the sweep deepened from 6 sub-layer cells to 488 individual objects (2026-06-20)
The 24-cell sub-layer matrix collapsed every object class into single cells (one "G3 I" cell stood for 54
DEFINER fns). `data_db_ufai_sweep.py` now enumerates and dispositions **every object individually**:
**488/488 objects covered · 0 gaps** — 147 tables (each: hive-RLS / personal-RLS / by-design / global-lookup),
249 public-schema policies (0 permissive-true bypass), 54 DEFINER fns (6 self-gate · 12 exempt · 36
no-hive-mutation, via the authoritative `validate_definer_tenant_gate` evaluator), 38 truth views (all
security_invoker). The 6×4 sub-layer matrix stays GREEN alongside (23 appl · 100% covered/verified · live 73.9%).

### ★ Per-object finding: `worker_achievements` was anon-readable platform-wide (the personal-class blind spot)
Deepening to per-object surfaced what the hive-only `validate_rls_coverage` scan structurally MISSED: a
**personal** table (`auth_uid`, no `hive_id`) with **RLS disabled + an inert `ach_worker_read USING(true)`
policy + anon SELECT** → any anonymous client could read every worker's XP/levels/activity across all hives
(proven live: anon `count(*)`=55). Evidence (achievements.html) said the intended visibility is **own +
same-hive standings**, not global — so `20260620000015` enables RLS with own (`auth_uid=auth.uid()`) +
same-hive (new `user_hive_worker_names()` DEFINER helper over `user_hive_ids()`). Writes go through
`award_achievement_xp` (DEFINER → unaffected); the own-row realtime sub survives. VERIFIED LIVE two-tenant
(Pablo hive-A: own 5 / peer 5 / cross-hive 0 / total 21; Leandro hive-B: own 3 / cross 0 / total 12; anon 0
was 55). `validate_rls_coverage.py` EXTENDED with the **PERSONAL class** (auth_uid-no-hive-id, RLS-off) so the
blind spot is now a permanent down-ratchet (teeth proven: RLS-off → REGRESSION exit 1).

### ★ G3 (U) RPC return-shape gate + G5 Accept (ratchet locked) (2026-06-20)
`tools/validate_rpc_return_shape.py` (NEW) — every app RPC must have an introspectable return shape; a bare
`RETURNS record`/`SETOF record` without OUT/TABLE params is opaque to PostgREST/callers (the U consumer
contract). Measured: **54 app RPCs · 44 strictly-typed · 10 json-by-choice · 0 opaque** (baseline 0 + blind
teeth). Registered in `run_platform_checks.py` (AI Validation) and folded into the sweep's G3/U cell (folds
**6/6 green**). The sweep now also enforces a **per-OBJECT forward-only ratchet** (covered may not fall / gaps
may not rise vs the locked baseline `{total:488, covered:488, gaps:0}`).

### ★ G2 live-isolation harness made type-agnostic (false "discover-error" fixed) (2026-06-20)
`validate_rls_tenant_isolation.py` discovery compared `t.hive_id = hm.hive_id` (uuid) and threw on the few
tables whose `hive_id` is **text** (rate-limit/trace keys) → a false `discover-error` skip that masked their
true state. Cast both sides `::text`. Now: `ai_user_rate_limits` → honest `single-hive` (it is isolated by
**user_id = auth.uid()**, not hive_id — a different key, proven by its policy), `wh_traces` → honest
`no-member-with-data` (empty edge-only table; isolation already ROLLBACK-verified in `…000004`). 41 tables
still test live, 0 LEAK, no regression. The remaining 55 skips are honest insufficient-dev-data (edge-only /
single-hive), not coverage gaps — the security-critical surface is live-tested (6/9 core) + ROLLBACK-verified
(3/9) + statically gated.

**Arc G phase state: G0✅ G1✅(I keystone) G2✅(F + isolation) G3✅(U return-shape) G4✅(A via validate_idempotency; value-lineage attributed to §13) G5✅(Accept — floors U/F/A/I all 100% verified vs 90/85/85/95; 488/488 per-object; 8 DB gates GREEN; ratchet locked).**

_NEXT (Ian-gated / forward-ratchet): whole-platform `run_platform_checks --full` (paid AI = Ian cost gate) · commit + `supabase db push` (16 migs) + `docker build` (Arc F). Local floor work complete._
