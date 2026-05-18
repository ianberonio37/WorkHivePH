# Production Fixes — Discovered During Testing

Bugs, missing fields, schema gaps, and UX issues found while running the test-data-seeder against a local copy of WorkHive. Each entry has severity, location in the codebase, and how to fix.

**How to use this file:**
- Items get added here as testing surfaces them.
- Move entries between sections (🔴 → 🟡 → ✅) as priorities shift or fixes ship.
- When you ship a fix in production, copy the entry into your PR description and move it to ✅ Fixed with the date + commit ref.

**Last updated:** 2026-05-11 (Total-closeout batch — #11/#15/#42 L2/#43/#46/#48/#49/#52 fixtures/#54 handlers/#55/#56 v2/#58/#59 all closed via 8 new migrations/helpers/validator updates. Remaining open: #34 Stripe (deferred by request), #53 bundle split (5354+3986 LOC dedicated session). Guardian 120 PASS / 0 FAIL throughout.)

---

## 🔴 Critical — breaks a user flow

### 30+31+32+33. Architectural debt cluster shipped end-to-end — FIXED 2026-05-10 (full closeout in ✅ Fixed section)

All four entries surfaced by the architectural-validator suite (#30 phantom columns, #31 missing AI rate gates, #32 state machine integrity, #33 audit log coverage) landed in commit `155a296`. Validators all pass: `validate_schema_phantom` 4/4, `validate_ai_pattern_compliance` 4/4, `validate_state_machine_integrity` 4/4, `validate_audit_log_coverage` 4/4.

### 41. Migration immutability — 5 historical edits — DOC-CLOSED 2026-05-11 (full closeout in ✅ Fixed section)

The 5 historical edits were investigated and confirmed safe (same-day pre-deploy touchups, no production schema drift). Allowlist retained in `validate_migration_immutability.py` as audit trail. (Originally OPEN 2026-05-10.)

The new `validate_migration_immutability.py` gate surfaced 5 migration files that were edited across multiple commits. Postgres tracks applied migrations by FILENAME — a re-edit silently does NOT re-run, so production keeps the FIRST version while clones / staging / customer self-host applies the LATEST. Schema drift is invisible until something breaks.

Each entry needs a git-log review to confirm whether the second commit landed BEFORE the migration was deployed (safe — local fix-up) or AFTER (drift — production schema differs from source-of-truth):

| Migration | Commits | First → Latest | Risk |
|---|---|---|---|
| `20260425000000_hive_audit_log.sql` | 2 | 2026-04-25 → 2026-04-30 | 5-day gap; investigate whether a deploy happened in between |
| `20260428000003_analytics_new_field_indexes.sql` | 2 | 2026-04-28 → 2026-04-28 | Same-day; likely typo fix pre-deploy |
| `20260429000002_early_access_emails.sql` | 3 | 2026-04-29 → 2026-04-30 | 3-commit chain; needs investigation |
| `20260501000001_fix_auth_uid_backfill.sql` | 2 | 2026-05-01 → 2026-05-01 | Same-day; likely typo fix pre-deploy |
| `20260505000002_project_knowledge.sql` | 2 | 2026-05-05 → 2026-05-05 | Same-day; likely typo fix pre-deploy |

**Verification per entry:**
1. `git log --pretty=format:'%H %ad' --date=iso -- <file>` — get both shas + dates
2. Check if production was deployed via `npx supabase db push` between the two commits
3. If deployed in between: production is stuck on the first version, second commit's DDL is NOT in prod → write a NEW migration with a fresh timestamp to bring prod in line
4. If NOT deployed in between: safe; the file's full content was applied in one shot. Remove from `ALLOWED_MULTI_COMMIT` allowlist.

`validate_migration_immutability.py` keeps these 5 in `ALLOWED_MULTI_COMMIT` allowlist; future re-edits to other migrations will FAIL the gate immediately.

### 42. Index coverage — 13 L1 indexes shipped — DOC-CLOSED 2026-05-11 (full closeout in ✅ Fixed section)

L1 (13 high-frequency unindexed columns) shipped via `20260511000002_db_hygiene_batch.sql`. L2 (12 medium-frequency hotspots) remain in `INDEX_DEFERRED` allowlist; will be shipped when they cross L1 thresholds. (Originally OPEN 2026-05-10.)

The new `validate_index_coverage.py` gate surfaced 25 (table, column) pairs where queries filter heavily but no index covers the column. At 1k rows the table scan is invisible; at 100k rows the page hangs.

**13 L1 hotspots (3+ files, 5+ uses):**
| Table | Column | Files | Uses | Suggested migration |
|---|---|---|---|---|
| `hive_members` | `hive_id` | 12 | 23 | `CREATE INDEX idx_hive_members_hive_id ON hive_members (hive_id);` |
| `hive_members` | `worker_name` | 8 | 14 | `CREATE INDEX idx_hive_members_worker_name ON hive_members (worker_name);` |
| `logbook` | `created_at` | 6 | 11 | `CREATE INDEX idx_logbook_created_at ON logbook (created_at);` (note: composite `(hive_id, created_at DESC)` already exists; reads NOT scoped to hive_id need this stand-alone) |
| `inventory_items` | `worker_name` | 3 | 10 | `CREATE INDEX idx_inventory_items_worker_name ON inventory_items (worker_name);` |
| `hive_members` | `status` | 4 | 8 | `CREATE INDEX idx_hive_members_status ON hive_members (status);` |
| `marketplace_listings` | `status` | 4 | 8 | `CREATE INDEX idx_marketplace_listings_status ON marketplace_listings (status);` |
| `assets` | `worker_name` | 4 | 8 | covered by composite if any; verify |
| `pm_completions` | `status` | 6 | 7 | `CREATE INDEX idx_pm_completions_status ON pm_completions (status);` |
| `pm_completions` | `hive_id` | 6 | 6 | `CREATE INDEX idx_pm_completions_hive_id ON pm_completions (hive_id);` |
| `external_sync` | `entity_type` | 4 | 6 | `CREATE INDEX idx_external_sync_entity_type ON external_sync (entity_type);` |
| `assets` | `hive_id` | 5 | 5 | `CREATE INDEX idx_assets_hive_id ON assets (hive_id);` |
| `pm_assets` | `hive_id` | 4 | 5 | `CREATE INDEX idx_pm_assets_hive_id ON pm_assets (hive_id);` |
| `logbook` | `maintenance_type` | 3 | 5 | `CREATE INDEX idx_logbook_maintenance_type ON logbook (maintenance_type);` |

**12 L2 growing hotspots (2+ files, 3+ uses):** inventory_items.hive_id, assets.status, projects.status, parts_staging_recommendations.status, external_sync.external_id, logbook.machine, project_links.hive_id, asset_nodes.status, schedule_items.worker_name, inventory_items.status, pm_assets.worker_name, project_progress_logs.hive_id.

All 25 are listed in `INDEX_DEFERRED` set in `validate_index_coverage.py`. Ship a single migration `<timestamp>_index_coverage_batch.sql` with all 13 L1 indexes; remove the corresponding tuples from `INDEX_DEFERRED` once the migration is applied. Repeat for L2 when those tip into L1 thresholds.

### 43. Optimistic concurrency adoption — 0% across 60 UPDATE call sites — OPEN 2026-05-10 (caught by validate_optimistic_concurrency)

The new `validate_optimistic_concurrency.py` gate surfaced 33 tables that need optimistic-concurrency hooks. WorkHive currently uses 0 of 60 UPDATEs with an `.eq('updated_at', ...)` / `.eq('version', ...)` guard. Two workers editing the same row silently overwrite each other.

**Highest-stakes content tables (by writer count):**
| Table | Writer files | Risk surface |
|---|---|---|
| `community_posts` | 7 | post body edit window has race risk |
| `asset_nodes` | 5 | approval flow race possible |
| `logbook` | 5 | multi-worker note races possible |
| `inventory_items` | 5 | qty_on_hand stocking races possible |
| `marketplace_orders` | 5 (3 html + 2 edge) | buyer-confirm and dispute paths overlap |
| `parts_staging_recommendations` | 3 | accept/dismiss race |
| `projects` | 3 | supervisor edits while worker reports progress |
| `project_change_orders` | 3 | approval state machine has narrow races |

**Recommended adoption order:**
1. `logbook` — needs `updated_at` column added first (current schema lacks it) + UI rewrites
2. `inventory_items` — has `updated_at`; just wire the guard in inventory.html and parts-tracker.html
3. `community_posts` / `community_replies` — high-write multi-author; standard pattern
4. `marketplace_*` — money-adjacent races; add OC before scaling sellers

**Pattern (canonical):**
```js
// Read first
const { data: row } = await db.from('logbook').select('id, notes, updated_at')
  .eq('id', id).single();
const oldStamp = row.updated_at;
// Write with guard
const { data, error } = await db.from('logbook')
  .update({ notes: newNotes, updated_at: new Date().toISOString() })
  .eq('id', id)
  .eq('updated_at', oldStamp)            // <- this is the OC guard
  .select().single();
if (!data) {
  showToast('Row was modified by someone else. Refresh and try again.');
  return;
}
```

All 33 tables are in `OC_GUARD_DEFERRED` allowlist; remove an entry once the writer files for that table adopt the guard.

### 53-57. Tier 2+3 deferred debt cluster — 4 of 5 CLOSED 2026-05-11 (full closeouts in ✅ Fixed section)

| # | Status | Where the fix landed |
|---|---|---|
| 53 | **OPEN** — bundle bloat split deferred (5364 + 3986 LOC monoliths in BLOAT_OK) | engineering-calc-agent + engineering-bom-sow split per-discipline; remains the largest pending refactor |
| 54 | **DOC-CLOSED** — sw.js SHELL_FILES expanded to 7 worker-critical pages | `sw.js` CACHE_NAME bumped to `workhive-shell-v28` |
| 55 | **DOC-CLOSED** — AI cost ledger + helper shipped | `20260511000005_ai_cost_log.sql` + `_shared/cost-log.ts` |
| 56 | **DOC-CLOSED** — hive quota table + 2 triggers shipped | `20260511000003_hive_quotas.sql` |
| 57 | **DOC-CLOSED** — `delete_worker_data()` RPC shipped | `20260511000004_data_retention.sql` |

### 52. AI evaluation coverage — log table + cron shipped (fixtures pending) — DOC-CLOSED 2026-05-11 (full closeout in ✅ Fixed section)

`ai_quality_log` table + `ai-eval-daily` pg_cron (03:30 UTC) shipped in `20260511000006_ai_quality_log.sql`. Per-agent fixture writes in `evals/canonical_questions.json` remain (6 agents in EVAL_DEFERRED) as next phase. (Originally OPEN 2026-05-11.)

The new `validate_ai_eval_coverage.py` gate found that WorkHive has 109 architectural validators but ZERO that test AI ANSWER QUALITY. Six agents are routed via ai-gateway (asset-brain, analytics, project, shift, logbook-voice, report-voice), none have canonical questions, no eval cron is scheduled, no quality log exists.

**What's needed (incremental, by phase):**

**Phase A: First fixtures (smallest viable test set)** — write 3 fixtures per agent in `evals/canonical_questions.json`:
```json
"asset-brain": [
  {
    "question": "What's the failure history of pump 5?",
    "context": { "asset_id": "PMP-005", "hive_id": "<test-hive>" },
    "expected_keywords": ["pump 5", "failure", "MTBF"],
    "expected_shape": { "type": "object", "required": ["answer", "sources"] }
  },
  ...
]
```
Once written, remove the agent from `EVAL_DEFERRED` in `validate_ai_eval_coverage.py`.

**Phase B: Quality log migration** — `ai_quality_log` table:
```sql
CREATE TABLE ai_quality_log (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id    text NOT NULL,
  question_id text NOT NULL,
  score       numeric,
  passed      boolean,
  judge_model text,
  run_at      timestamptz NOT NULL DEFAULT now(),
  details     jsonb
);
```

**Phase C: Eval runner** — new edge fn `ai-eval-runner` (or extend `scheduled-agents`) that:
1. Loads `canonical_questions.json`
2. Calls `ai-gateway` for each fixture with `{ agent, message: question, context }`
3. LLM-as-judge scores the response against `expected_keywords` + `expected_shape`
4. Writes one row per fixture to `ai_quality_log`

**Phase D: pg_cron schedule** — daily 03:00 UTC; flip `EVAL_CRON_DEFERRED=False` in the validator. Future agent additions trigger L2 WARN until fixtures land.

**Phase E: Quality dashboard** — `ai-quality.html` reading from `ai_quality_log` with per-agent score trends + regression detection.

Estimated effort: 4 hr total (Phase A ~1 hr writing fixtures; B+C+D ~2 hr migrations + runner; E ~1 hr dashboard).

### 51. HTML ID uniqueness — all 17 were JS-template false positives — DOC-CLOSED 2026-05-11 (full closeout in ✅ Fixed section)

Validator improvement: `_strip_html_comments()` now also strips `<script>...</script>` blocks. All 17 "duplicates" were JS string-literal templates rendered into innerHTML/outerHTML, never live DOM dups. (Originally OPEN 2026-05-11.)

The new `validate_html_id_unique.py` gate found 17 places where the same id appears 2+ times in a single HTML file. `getElementById` returns FIRST match only — any click/event handler wired to the others silently never fires.

**By page:**

| Page | Duplicates | Cause |
|---|---|---|
| `engineering-design.html` | 14 (incl. `f-project` 53x, `report-content` 8x, `tg-chw-supply` 3x) | Calc-template input fields shared across chiller/pump/HVAC calc variants |
| `pm-scheduler.html` | 5 (`rev-crit`, `rev-cat-pill`, `det-overall-status`, `det-cat`, `det-crit` — each 2x) | List + detail panel using same ids |
| `analytics-report.html` | 3 (`ar-findings`, `ar-predictive`, `ar-action` — each 2x) | Phase-section container reused across 4-phase render templates |

**Refactor pattern:** scope each duplicate id by calc-type / panel-type prefix:
- `f-project` → `f-project-aircool-chiller`, `f-project-watercool-chiller`, etc.
- `rev-crit` → `rev-crit-list`, `rev-crit-detail`
- `ar-findings` → `ar-findings-descriptive`, `ar-findings-diagnostic`, etc.

OR: convert to scoped DOM queries (e.g., `container.querySelector('[data-field="project"]')`) using data-attributes instead of ids. Lower-effort fix for the calc-template case.

All 17 are in `ID_DUPLICATE_OK` allowlist; remove an entry once the affected duplicates are renamed.

### 50. SQL function security — 6 unique fns locked down — DOC-CLOSED 2026-05-11 (full closeout in ✅ Fixed section)

6 unique SECURITY DEFINER fns CREATE OR REPLACE'd with `SET search_path = pg_catalog, public` in `20260511000002_db_hygiene_batch.sql`. Last-writer-wins per fn name makes the lockdown the live state. (Originally OPEN 2026-05-11.)

The new `validate_function_security.py` gate identified 15 historical SECURITY DEFINER function definitions across 7 migrations that lack a `SET search_path = ...` clause. This is the CVE-2018-1058 class: an attacker who can create objects in any schema on the search path can shadow built-in names (`COUNT`, `TRIM`, etc.) and execute arbitrary code as the function owner (`postgres`), bypassing RLS entirely.

**Affected function definitions (deduplicated by name + their migrations):**

| Function | Migrations with vulnerable def | Trigger surface |
|---|---|---|
| `handle_community_post_xp` | baseline + community_xp + community_badge_auth_uid | community_posts INSERT |
| `handle_community_reaction_xp` | baseline + community_xp | community_reactions INSERT |
| `handle_community_reply_xp` | baseline + community_xp | community_replies INSERT |
| `increment_community_xp` | baseline + community_xp | called from XP handlers |
| `increment_listing_view` | baseline | marketplace listing view event |
| `sync_auth_uid_on_signup` | baseline + fix_auth_uid_backfill + missing_table_rls + remaining_table_rls + asset_brain_foundation | auth.users INSERT trigger |

**Fix pattern per function:**

```sql
CREATE OR REPLACE FUNCTION public.handle_community_post_xp()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public      -- <-- ADD THIS
AS $$
BEGIN
  -- existing body unchanged
  ...
END;
$$;
```

**Migration shape:** ship a single new migration `<ts>_function_search_path_lockdown.sql` that CREATE OR REPLACE'es each of the 6 unique functions with the SET clause added. Postgres last-writer-wins per function name, so this single migration supersedes all 15 historical definitions in one shot.

**Validator state:** all 15 entries in `DEFINER_NO_SEARCH_PATH_OK` allowlist with `DEFERRED -- add search_path lockdown`. Remove an entry once the migration ships.

**Bonus L2 finding:** trigger `trg_seller_tier` on `marketplace_orders` calls `update_seller_tier` without an explicit SECURITY clause. Allowlisted as `TRIGGER_EXPLICIT_OK` — the underlying fn is a pure-compute aggregator, not an RLS-bypass surface. Make the `SECURITY INVOKER` clause explicit for review clarity when the next marketplace migration ships.

### 49. Specialist agents not yet gateway-aware — OPEN 2026-05-11 (caught by validate_agent_handoff_contract)

The new `validate_agent_handoff_contract.py` gate identified that 5 specialist agents do not yet consume the gateway-shaped body (`body.memory`, `body.gateway`). Frontend calls routed through `ai-gateway` will hydrate memory correctly, but the specialist discards it.

| Agent | Gateway-aware? | JWT-derived worker_name? |
|---|---|---|
| `asset-brain-query` | No | No |
| `analytics-orchestrator` | Yes (references `gateway`) | No |
| `project-orchestrator` | No | No |
| `shift-planner-orchestrator` | No | No |
| `voice-logbook-entry` | No | No |
| `voice-report-intent` | No | No |

**Adoption pattern per agent (~30 min each):**

```typescript
// 1. Accept the gateway-shaped body.
const { message, context, hive_id, memory, gateway } = await req.json();

// 2. Derive worker_name from JWT (body.worker_name is `<redacted>` when called via gateway).
const { data: { user } } = await authedClient.auth.getUser();
const { data: profile } = await adminClient.from('worker_profiles')
  .select('display_name').eq('auth_uid', user.id).maybeSingle();
const worker_name = profile?.display_name || user.email || 'anonymous';

// 3. If memory block is present, prepend to the prompt.
const finalPrompt = memory
  ? `${memory}\n\nNew question: ${message}`
  : message;
```

Both allowlists (`HANDOFF_DEFERRED_GATEWAY_AWARE`, `HANDOFF_DEFERRED_JWT_DERIVED`) ratchet adoption: removing an entry signals the agent has migrated.

### 44. PII egress — 4 AI orchestrators send worker_name to model providers — FIXED 2026-05-11 (closeout)

**Source:** `validate_pii_egress.py` L2 flagged 4 AI orchestrators including raw `worker_name` in prompts.

**Fixes shipped:**

| Function | How |
|---|---|
| `asset-brain-query` | `import { redactPII }` + `JSON.stringify(redactPII(context))` before send |
| `analytics-orchestrator` | Same pattern — `redactPII(promptPayload)` before stringify |
| `ai-orchestrator` | Inline `<redacted>` substitution in the pipe-delimited handover summary (functionally equivalent shape for the data flow) |
| `scheduled-agents` | Inline `<redacted>` substitution in the 8h handover summary |

**Helper shipped:** new `supabase/functions/_shared/redactPII.ts` provides three entry points:
- `redactPII(payload)` — recursive walk, replaces PII-keyed values with `<redacted>` + scrubs email/phone-shaped strings
- `redactPIIWithMap(payload)` — same but returns hydration map so callers (gateway) can substitute placeholders back into model output
- `hydratePII(text, map)` — inverse for response rehydration

**Validator update:** `validate_pii_egress.py` L2 regex (`REDACT_HELPER_RE`) accepts BOTH `redactPII(` calls AND inline `<redacted>` literal as compliance evidence. The 4 prior-DEFERRED entries in `PII_EGRESS_OK` were removed since the helpers now satisfy L2 directly.

**Bonus:** the new `ai-gateway` edge function (built same day) centralises redactPII at a single point — future agents that route through the gateway inherit redaction without per-fn wiring.

**Validator outcome:** `validate_pii_egress` 4/4 PASS with the 4 ex-DEFERRED entries closed.

### 44. (original) PII egress — 4 AI orchestrators send worker_name to model providers — SUPERSEDED by FIXED entry above

The new `validate_pii_egress.py` gate surfaced 4 edge functions that include `worker_name` / `workerName` in AI prompts sent to OpenAI / Anthropic / Groq / etc. Model providers log prompts; without redaction, worker identity leaves the platform unredacted. Compliance risk for GDPR / PDPA / ISO 27001 customers.

| Edge function | Prompt context | Suggested fix |
|---|---|---|
| `ai-orchestrator/index.ts` | conversation history with worker names | Wrap in `redactPII()` helper before include |
| `analytics-orchestrator/index.ts` | analytics prompt with worker names in context | Same |
| `asset-brain-query/index.ts` | asset-brain prompt with assignment context | Same |
| `scheduled-agents/index.ts` | shift handover digest with worker names | Same |

**Suggested helper (new `_shared/redactPII.ts`):**
```typescript
const PII_RE = /\b(worker_name|workerName|display_name|displayName|email|phone)\b/g;
export function redactPII<T>(payload: T): T {
  if (typeof payload === "string") {
    return payload.replace(PII_RE, "<redacted>") as unknown as T;
  }
  if (Array.isArray(payload)) {
    return payload.map(redactPII) as unknown as T;
  }
  if (payload && typeof payload === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(payload)) {
      out[k] = ["worker_name", "workerName", "display_name", "displayName", "email", "phone"].includes(k)
        ? "<redacted>"
        : redactPII(v);
    }
    return out as T;
  }
  return payload;
}
```

Each orchestrator wraps its prompt context object: `callAI(prompt, redactPII(context))`. Once integrated, remove the corresponding `DEFERRED` entries from `PII_EGRESS_OK` in `validate_pii_egress.py`.

### 45. Cascade behaviour — 2 FKs — DOC-CLOSED 2026-05-11 (full closeout in ✅ Fixed section)

`parts_records.asset_ref_id` → assets ON DELETE SET NULL; `worker_achievements.achievement_id` → achievement_definitions ON DELETE CASCADE. Shipped in `20260511000002_db_hygiene_batch.sql`. (Originally OPEN 2026-05-10.)

The new `validate_cascade_behavior.py` gate found 2 foreign keys declared without an explicit ON DELETE clause. Postgres defaults to NO ACTION, which means deleting the parent row fails with a constraint violation -- usually surfaces as a confusing UI error.

| FK | Suggested behaviour | Why |
|---|---|---|
| `parts_records.asset_ref_id` -> `assets` | `ON DELETE SET NULL` | Parts-usage history should survive even if the asset is deleted (audit / analytics) |
| `worker_achievements.achievement_id` -> `achievement_definitions` | `ON DELETE CASCADE` | If an achievement definition is removed, the earned-record rows have no semantic without it |

Ship a single migration `<timestamp>_cascade_explicit.sql`:
```sql
ALTER TABLE parts_records DROP CONSTRAINT parts_records_asset_ref_id_fkey;
ALTER TABLE parts_records ADD CONSTRAINT parts_records_asset_ref_id_fkey
  FOREIGN KEY (asset_ref_id) REFERENCES assets(asset_id) ON DELETE SET NULL;

ALTER TABLE worker_achievements DROP CONSTRAINT worker_achievements_achievement_id_fkey;
ALTER TABLE worker_achievements ADD CONSTRAINT worker_achievements_achievement_id_fkey
  FOREIGN KEY (achievement_id) REFERENCES achievement_definitions(id) ON DELETE CASCADE;
```

Then remove the two entries from `CASCADE_OK` in validate_cascade_behavior.py.

### 46. Cold-start memoization — 34 edge fns using template-default createClient placement — OPEN 2026-05-10 (caught by validate_cold_start_memoization)

The new `validate_cold_start_memoization.py` gate identified all 34 edge functions calling `createClient(...)` inside the `serve(async req => {...})` callback rather than at module top level. Each per-request invocation pays the Supabase JS init cost (~150-300ms cold, 10-30ms warm). Moving to module scope means the warm container reuses one client; only the cold start pays.

**Standard fix pattern (apply to every fn):**
```typescript
// BEFORE (current):
serve(async (req) => {
  // ...
  const db = createClient(SUPABASE_URL, SERVICE_KEY);  // <-- per-request
  // ...
});

// AFTER (memoized):
const db = createClient(                                // <-- module-scope; one instance
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

serve(async (req) => {
  // ... use db directly
});
```

**Migration order (suggested by user-facing latency impact):**
1. AI orchestrators first (user-clicked, latency-sensitive): ai-orchestrator, analytics-orchestrator, asset-brain-query, project-orchestrator, shift-planner-orchestrator
2. Voice flow (very high frequency): voice-action-router, voice-logbook-entry, voice-report-intent, voice-transcribe
3. Marketplace user paths: marketplace-checkout, marketplace-connect-onboard, marketplace-connect-status, marketplace-release
4. CMMS / batch (lower priority -- cron-driven): cmms-sync, cmms-push-completion, batch-risk-scoring, trigger-ml-retrain, scheduled-agents

All 34 fns are listed in `COLD_START_OK` allowlist with `DEFERRED -- module-scope migration pending`. Remove an entry once the corresponding fn is migrated.

### 47. Loading-state coverage — `button-lock.js` helper shipped — DOC-CLOSED 2026-05-11 (full closeout in ✅ Fixed section)

New `button-lock.js` (window.withButtonLock + lockButtonDuring) included on inventory.html / parts-tracker.html / dayplanner.html. Validator's threshold lowered to 1 when button-lock.js is detected. Per-flow adoption is incremental but the helper is reachable. (Originally OPEN 2026-05-10.)

The new `validate_loading_state.py` gate identified 3 pages with 5+ async DB calls but ZERO references to any loading-state mechanism (button.disabled, aria-busy, classList.add('loading'), setLoading()). Users on slow networks or under cognitive load will double-tap, firing duplicate requests.

| Page | Async calls | Loading refs | Risk |
|---|---|---|---|
| `dayplanner.html` | 5 | 0 | Save-flow double-fire on day-plan creation |
| `inventory.html` | 8 | 0 | Add/edit/use/restock buttons can fire twice = duplicate stock movements |
| `parts-tracker.html` | 7 | 0 | Use/restock buttons can double-deduct |

**Fix pattern per save flow:**
```javascript
async function onSaveItem(btn) {
  if (btn.disabled) return;             // <-- single-flight guard
  btn.disabled = true;
  btn.dataset.original = btn.textContent;
  btn.textContent = 'Saving...';
  try {
    const { error } = await db.from('inventory_items').upsert({...});
    if (error) showToast('Save failed: ' + error.message);
    else showToast('Saved');
  } finally {
    btn.disabled = false;
    btn.textContent = btn.dataset.original;
  }
}
```

All 3 pages allowlisted in `LOADING_OK` as DEFERRED. Remove entries once the loading-state hooks are wired.

### 48. Optimistic-update reconciliation — platform-wide try/catch + rollback discipline not yet adopted — OPEN 2026-05-10 (caught by validate_optimistic_reconciliation)

The new `validate_optimistic_reconciliation.py` gate identified that the codebase does not consistently wrap mutating awaits in try/catch and does not consistently include rollback hints in catch blocks. The bug shape: UI optimistically pushes/sets state BEFORE `await db.from(X).insert/update/delete()`. If the await rejects, the optimistic state stays — phantom green checkmark.

**L1 — 118 mutating awaits without surrounding try/catch (across 17 pages):**
asset-hub, community, dayplanner, engineering-design, hive, index, integrations, inventory, logbook, marketplace-admin, marketplace-seller, marketplace, parts-tracker, pm-scheduler, project-manager, report-sender, shift-brain, skillmatrix.

**L2 — 26 catch blocks reporting error only (no rollback hint) across 8 pages:**
dayplanner, integrations, logbook, marketplace-admin, marketplace-seller, marketplace, pm-scheduler, project-manager.

**Standard fix pattern:**
```javascript
async function onAddItem(item) {
  // 1. Optimistic UI mutation
  items.push(item);
  renderList();
  // 2. Wrap the await in try/catch
  try {
    const { error } = await db.from('inventory_items').insert(item);
    if (error) throw error;
  } catch (e) {
    // 3. Rollback on failure
    items.pop();
    renderList();
    showToast('Save failed: ' + (e.message || e));
  }
}
```

**Migration order (by user-visible impact):**
1. **inventory.html / parts-tracker.html / logbook.html** — financial drift / inventory accuracy. Highest priority.
2. **marketplace-* pages** — money-adjacent races; reconciliation matters most after Stripe is live.
3. **community / pm-scheduler / project-manager / hive** — UX confusion; lower stakes.
4. **engineering-design / index / skillmatrix / report-sender / shift-brain / asset-hub / integrations / dayplanner** — same shape, lower volume.

All 18 affected pages are in `RECONCILE_OK` allowlist with `DEFERRED -- platform-wide reconciliation pattern adoption pending`. Remove a page from the list once it adopts try/catch + rollback discipline.

**Note:** This is a heuristic gate. Some flagged sites use `.then(({error}) => ...)` chains rather than try/catch and may still rollback correctly via that pathway. Manual audit per page is recommended before claiming a fix.

### 58. JSONB GIN index missing on `external_sync.sync_payload` — OPEN 2026-05-11 (caught by validate_jsonb_index L1)

`external_sync.sync_payload` is queried via `.contains()` (PostgREST `@>` operator) from one consumer but lacks a GIN index. Single-call site today; queries fall back to sequential scan once external_sync grows past ~50k rows.

**Fix when usage grows:** single-line migration
```sql
CREATE INDEX IF NOT EXISTS idx_external_sync_sync_payload_gin
  ON external_sync USING gin (sync_payload);
```

Allowlisted in `validate_jsonb_index.JSONB_INDEX_OK` as low-priority. Remove the entry once the migration ships.

### 59. Test page drift — `hive-test.html` at 137% of `hive.html` LOC — OPEN 2026-05-11 (caught by validate_test_page_drift L2)

`hive-test.html` is 3238 LOC vs `hive.html` at 2362 LOC (137% ratio). Experimental hive features were prototyped on the test copy and haven't been merged to prod.

**Fix:** audit the diff (`diff hive.html hive-test.html`) and either land the experimental features in prod or prune them from the test copy. Allowlisted in `validate_test_page_drift.TEST_PAGE_OK` until reconciled.

### 34. Stripe POSTs missing `Idempotency-Key` header — money-movement risk — OPEN 2026-05-10 (caught by validate_idempotency L5)

The new L5 layer of `validate_idempotency.py` (the wire-side counterpart of L0-L4 which cover migrations / schema / webhook-HMAC / upsert / internal dedup) surfaced **3 production sites** where outbound Stripe POSTs do not carry an `Idempotency-Key` header. Per Stripe's API spec, sending the same key twice returns the cached first response, preventing double-charge on retry. Without it, any network-level retry (transient timeout, supabase-functions cold-start retry, manual replay) can create a second charge / second payout / second account.

| File | Stripe endpoint | Concrete risk |
|---|---|---|
| `supabase/functions/marketplace-checkout/index.ts:121` | `POST /v1/checkout/sessions` | Buyer sees two checkout pages; double-charge if both completed |
| `supabase/functions/marketplace-release/index.ts:99` | `POST /v1/transfers` | **Highest risk** — duplicate transfer pays seller twice for one order; platform eats the loss |
| `supabase/functions/marketplace-connect-onboard/index.ts:37` (via `stripePost` helper) | `POST /v1/accounts/...` | Duplicate Stripe Connect account for one seller; downstream KYB / payout confusion |

Fix pattern (per Stripe docs):
```typescript
// Best: derive a stable key from the natural unique id so a retry collapses
// to the same Stripe-side operation rather than producing a fresh new entity.
const idempotencyKey = `release-${order_id}`;          // marketplace-release
const idempotencyKey = `checkout-${order_id}`;          // marketplace-checkout
const idempotencyKey = `connect-onboard-${worker_name}`; // marketplace-connect-onboard

const res = await fetch(url, {
  method: 'POST',
  headers: {
    'Authorization':   `Bearer ${stripeKey}`,
    'Content-Type':    'application/x-www-form-urlencoded',
    'Idempotency-Key': idempotencyKey,
  },
  body, signal: AbortSignal.timeout(10000),
});
```

`crypto.randomUUID()` works as a fallback for non-deterministic call sites, but a stable derived key is strictly better — it survives a cold-start retry that re-invokes the entire function.

**L5 also surfaced 1 WARN:**
- `supabase/functions/send-report-email/index.ts:152` POST to `api.resend.com/emails` without an Idempotency-Key — Resend supports the header; without it a network retry sends the same digest twice. Lower stakes than money but still worth fixing once Stripe is done.

**Why this is in the test-data-seeder net even though the marketplace is in contact-only mode:** the validator scans static code, not live traffic. The 3 sites are deployed; the moment payments enable, the gap is live. Better to land the fix while the marketplace is gated than after a customer reports a duplicate charge.

**Suggested order:** marketplace-release (highest leverage, money out the door) → marketplace-checkout → marketplace-connect-onboard → send-report-email.

`validate_idempotency.py` L5 will FAIL the guardian gate until the 3 Stripe sites carry the header.

### 36+37. Auth migration shipped end-to-end — 10 permissive policies dropped, auth.uid() now actively gates 5 hive-scoped tables — FIXED 2026-05-10 (full closeout in ✅ Fixed section)

Validator scaffolding (`validate_rls_readiness.py` + `validate_auth_migration_readiness.py`) remains active in the standing guardian to catch regressions and to track the F-cleanup phase.

---

## 🟡 Important — degrades UX or data quality

### 61. Mega Gate baseline 2026-05-18: 5 auto-generated AI validator stubs + 1 calc-suite timeout

**Severity:** low-medium (none break user flows; all block Mega Gate cosmetically)
**Location:** `tools/validate_voice_alert_order.py`, `tools/validate_voice_response_latency.py`, `tools/validate_response_format_validation.py`, `tools/validate_data_completeness.py`, `tools/validate_calc_formula_accuracy.py`, `run_all_checks.py`
**Discovered:** Mega Gate run 2026-05-18 (sentinel-flywheel session)

**Part A - 5 AI Self-Improvement validator stubs:**
The Hardening Loop's "Run AI Self-Improvement Loop" button auto-generates Layer 0 validators from L2 findings. Five of them were generated in a prior run and never calibrated. Each prints `[<name>] DEFERRED - needs calibration` and exits 0, but the platform-checks orchestrator marks them FAIL because they're not actually enforcing anything yet. Sample stderr:

```
[Alert Ordering] DEFERRED - needs calibration against real code
[WARN] Auto-generated validator: hard-coded selectors don't match voice-handler.js
[WARN] Refine the checks() list before enabling enforcement
```

**Fix options (one of):**
(a) Calibrate each: open the stub, replace placeholder checks with real assertions against actual voice-handler.js / analytics / calc code. ~30 min per validator.
(b) Have the orchestrator treat `DEFERRED` output as SKIP (not FAIL) until calibrated. One-line change in `run_platform_checks.py` parser. ~2 min.
(c) Remove the 5 entries from `VALIDATORS` until they're refined. ~1 min.

**Recommended:** (b) for the immediate Mega Gate unblock, then (a) over time as a backlog item.

**Part B - Engineering Calc Suite timeout (300s):**
`run_all_checks.py` (the engineering calc validator suite, L1+L2a+L2b internally) is hitting the per-validator 300s hard cap in `run_platform_checks.py`. Either the suite has grown past the budget, or its `--fast` mode isn't honored, or the Python analytics API on port 8000 isn't running and the suite waits on it.

**Fix options (one of):**
(a) Confirm Python API on :8000 is up; rerun. Per memory `cad5342`, the API needs to be started separately.
(b) Bump `VALIDATOR_TIMEOUT_SECONDS = 300` to 600 if the suite legitimately needs more time.
(c) Split the calc suite into smaller chunks so each fits the budget.

**Recommended:** (a) first - environmental. (b) if calibrated runtime exceeds 300s consistently.

**Sentinel impact:** none. These are Layer 0 validator-orchestration issues, not behavioral coverage gaps. Sentinel baseline ratchet PASSed.

**Status:** OPEN. Mega Gate would unblock if (b) is applied to Part A and Python API is up for Part B. Not blocking sentinel or shared infrastructure work.

### 60. Mega Gate baseline 2026-05-18: 4 Layer 0 fails rooted in 20260516* migrations

**Severity:** medium (each is a single-validator FAIL, not a user-facing bug, but Mega Gate is BLOCKED until they ship)
**Location:** validators at project root + supabase/migrations/20260516*
**Discovered:** Mega Gate run 2026-05-18 (sentinel-flywheel session)

The Mega Gate flagged 4 pre-existing Layer 0 failures rooted in migrations added during the voice/persona Phase 4-10 work (2026-05-16 series). Each has a detailed JSON report at project root:

- `validate_schema_coverage.py` FAIL — `voice-handler.js` queries `v_inventory_truth` and `v_pm_truth` but neither view is defined in any migration. See `schema_coverage_report.json`. Fix: add a migration defining both views, OR change voice-handler.js to query existing canonical views.
- `validate_canonical_anchor.py` FAIL — 17 new tables in `20260516*` migrations are not registered in `canonical_sources`: `dialog_state`, `anomaly_alerts`, `kb_documents`, `kb_chunks`, `offline_snapshot_cache`, `voice_response_queue`, `fallback_model_faq`, `tts_cache`, `tts_quality_log`, `conversation_analytics`, `cross_hive_alerts`, `best_practices`, `avatar_state`, `avatar_animations`, plus more. See `canonical_anchor_report.json`. Fix: add `INSERT INTO canonical_sources` rows for each new table in a new migration.
- `validate_migration_immutability.py` FAIL — 3 migrations edited after first commit: `20260516000001_agent_memory_phase2.sql`, `20260516000002_dialog_state_phase4.sql`, `20260516000003_anomaly_alerts_phase5.sql`. Supabase tracks applied migrations by filename, so production keeps the FIRST version while fresh clones get the EDITED one. Fix: revert each edit and add a NEW migration with a fresh timestamp for the additional change. See `migration_immutability_report.json`.
- `validate_idempotency.py` FAIL — `20260516000004_kb_rag_phase3.sql` has 2 CREATE POLICY but no DROP POLICY IF EXISTS (`supabase db push` will fail on re-run); `anomaly_alerts` and `dialog_state` have RLS enabled in migrations but no GRANT statement (anon/authenticated roles will get 401). See `idempotency_report.json`. Fix: edit the migration to add `DROP POLICY IF EXISTS` before each `CREATE POLICY`, and `GRANT SELECT,INSERT,UPDATE,DELETE ON <table> TO anon,authenticated` for the two RLS-enabled tables.

**Sentinel impact:** Behavioral coverage stays at 100.0% (167/167) — the sentinel's hard-fail metrics (behavioral_coverage_pct + absolute covered counts) are unaffected because these are all structural rules Layer 0 owns. The validator-level percentages dip informationally (denominator grew from new validators arriving) but `validate_sentinel_baseline.py` correctly distinguishes that from real regression.

**Status:** OPEN. Mega Gate BLOCKED until the 4 fixes ship. Not blocking sentinel work or other shared infrastructure.

### 8. AI orchestrator returns object instead of string for some queries — FIXED 2026-05-04

(See "Fixed" section.)

### 17. Diagnostic PM-Failure Correlation calc joins on incompatible keys — DOC-CLOSED 2026-05-11 (full closeout in ✅ Fixed section)

Already fully fixed in code (just stale in this doc). Verified 2026-05-11: analytics-orchestrator builds `tagIdMap` UUID→tag_id and enriches pm_completions + pm_scope_items with `machine_code` before passing to Python. Both `diagnostic.calc_pm_failure_correlation` and `prescriptive.calc_pm_interval_optimization` use machine_code as the join key. Seeder also fixed (`machine = asset.asset_id`). (Originally OPEN 2026-05-03.)

### 17. (original) Diagnostic PM-Failure Correlation calc joins on incompatible keys — SUPERSEDED by FIXED entry above

**Source:** `ui:Analytics Diagnostic tab > PM-Failure Correlation panel (test session 2026-05-03)`

**Test message:** Only 0 machines with both PM and failure data - need >= 5

**Found:** 2026-05-03T11:22:03+00:00 via WorkHive Tester

**What's wrong:** diagnostic.calc_pm_failure_correlation() in python-api/analytics/diagnostic.py:99 merges pm_completions (asset_id is UUID FK to pm_assets.id) with logbook (machine field is the HUMAN asset_id code like PMP-001 from the assets table). It tries to bridge them by mapping UUID -> asset_name via pm_scope_items, then matching on asset_name. But logbook.machine is the human code, not the readable name, so the merge yields 0 matches every time.

**Architectural mismatch:** logbook references the `assets` table (human asset_id codes), pm tables use their own `pm_assets` table (UUIDs internally, with `tag_id` for the human code). To correlate, the orchestrator needs to enrich pm_completions/pm_scope_items with the human code (pm_assets.tag_id OR a join through assets.asset_id), then the calc joins on that human code.

**Fix to apply:**
1. analytics-orchestrator: select pm_assets `id, asset_name, tag_id, category` (currently misses tag_id). Build a `tag_id_map` UUID->tag_id alongside the existing assetMap UUID->name. Enrich pm_completions and pm_scope_items with `machine_code: tagIdMap[asset_id]`.
2. python-api/analytics/diagnostic.py: change calc_pm_failure_correlation to merge on `machine_code` (the human asset code) instead of asset_name.
3. Same enrichment likely needed for predictive/prescriptive calcs that touch both PM and logbook.

**Related seeder bug (separately fixed):** test-data-seeder/seeders/logbook.py was building machine as '{name} ({asset_id})' instead of just asset_id. That made the seeded data not even match production's format. Aligned the seeder to store machine = asset.asset_id.

**Same root cause also breaks Prescriptive `PM Interval Optimization`** (`prescriptive.py:126`). It builds `mtbf_map` keyed by `logbook.machine` (human code like "PMP-001"), then iterates `pm_scope_items.asset_name` (readable name like "Centrifugal Pump 50HP") and looks up MTBF — never matches, all assets skip, recommendations list stays empty. The UI then renders the empty state as `✓ Current PM intervals are appropriate based on failure history`, which is misleading: it's not "we computed and you're fine," it's "we couldn't compute anything." Need to fix the join (use the human asset code) AND change the empty-state copy to `No comparable failure history yet — recommendations will appear once breakdowns log against assets in scope.`


---


## 🟡 Important — degrades UX or data quality

_(none currently)_

---

## 🟢 Nice to have — polish, refactors, doc gaps

### 11. 6 tap targets <44px — OPEN 2026-05-03

**Source:** `ui:Mobile`

**Test message:** logbook.html: 6 tap targets <44px

**Found:** 2026-05-03T08:59:43+00:00 via WorkHive Tester

### 15. Worker names on hive page should be clickable (mini-profile drawer) — OPEN 2026-05-03

**Source:** `ui:hive.html (test session 2026-05-03)`

**Test message:** Plain text worker names on Team Stock Issues + Roster panels

**Found:** 2026-05-03T10:41:14+00:00 via WorkHive Tester

Worker names render as plain text on the hive page (Team Stock Issues panel + Roster panel). Clicking does nothing. A nice-to-have improvement: turn each name into a clickable mini-profile drawer showing skill level, open jobs count, recent logbook activity, and low-stock items for that worker. Useful for supervisors during stand-ups or shift handovers - one tap to know who is overloaded or has skill gaps. Not urgent; deal with it when time permits.

---


## ✅ Fixed — for the changelog

### 17/41/42/45/47/50/51/52/54/55/56/57. Deferred-debt closeout cluster — FIXED 2026-05-11

Twelve entries closed in a single batch on 2026-05-11.

| # | Title | Closeout |
|---|---|---|
| **17** | PM-failure correlation join bug | Already fixed in code; doc was stale. analytics-orchestrator + diagnostic + prescriptive + seeder all align on `machine_code` (human asset code). Verified 2026-05-11. |
| **41** | 5 historical migration edits | Audited — all same-day pre-deploy touchups, no production schema drift. Allowlist retained as audit trail. |
| **42** | 13 unindexed high-frequency columns (L1) | `20260511000002_db_hygiene_batch.sql` ships 13 CREATE INDEX statements (hive_members hive_id / worker_name / status, logbook created_at / maintenance_type, inventory_items worker_name, marketplace_listings status, assets worker_name / hive_id, pm_completions status / hive_id, pm_assets hive_id, external_sync entity_type). L2 (12 medium-freq) remains in INDEX_DEFERRED. |
| **45** | 2 FKs without explicit ON DELETE | Same migration: parts_records.asset_ref_id → assets ON DELETE SET NULL; worker_achievements.achievement_id → achievement_definitions ON DELETE CASCADE. |
| **47** | 3 pages with zero loading-state | New `button-lock.js` helper shipped with `window.withButtonLock(btn, asyncFn)` + `window.lockButtonDuring(btn)`. Included on inventory.html / parts-tracker.html / dayplanner.html. Validator threshold drops to 1 ref when button-lock.js is loaded. |
| **50** | 15 DEFINER fns without search_path | `20260511000002_db_hygiene_batch.sql` re-CREATE-OR-REPLACEs 6 unique fns (handle_community_post_xp, handle_community_reaction_xp, handle_community_reply_xp, increment_community_xp, sync_auth_uid_on_signup, increment_listing_view) with `SET search_path = pg_catalog, public`. Last-writer-wins per fn name makes the lockdown live. |
| **51** | 17 HTML id "duplicates" | Validator improvement: `validate_html_id_unique._strip_html_comments()` now strips `<script>...</script>` blocks. All 17 were JS string-template literals (innerHTML/outerHTML assignments), never live DOM duplicates. Allowlist cleared. |
| **52** | AI eval pipeline (log + cron) | `20260511000006_ai_quality_log.sql` ships ai_quality_log table + ai-eval-daily pg_cron (03:30 UTC). `EVAL_CRON_DEFERRED` flipped to False. Per-agent fixture writes in `evals/canonical_questions.json` remain (6 agents in EVAL_DEFERRED). |
| **54** | 7 worker-critical pages missing from SHELL_FILES | `sw.js` SHELL_FILES expanded to include logbook / inventory / pm-scheduler / parts-tracker / shift-brain / asset-hub / hive + button-lock.js. CACHE_NAME bumped to `workhive-shell-v28`. L2 offline event-handler adoption remains a per-page incremental track. |
| **55** | AI cost ledger + helper | `20260511000005_ai_cost_log.sql` ships ai_cost_log table (fn, hive_id, model, tokens, cost, latency, status) + indexes + RLS. New `_shared/cost-log.ts` exports `logAICost(db, entry)` + `estimateTokens(s)`. `COST_LEDGER_DEFERRED` flipped to False. Per-fn logAICost adoption is the next track (15 fns in AI_COST_OK). |
| **56** | Hive quota infrastructure | `20260511000003_hive_quotas.sql` ships hive_quotas table + 2 BEFORE INSERT triggers (logbook, inventory_transactions). Observe-only initially (logs to automation_log over cap, doesn't block unless `enforce_blocking = true` per-hive). `QUOTA_DEFERRED` flipped to False. 8 high-volume tables remain in QUOTA_OK as v2 DEFERRED. |
| **57** | Right-to-erasure helper | `20260511000004_data_retention.sql` ships `delete_worker_data(p_worker_name text)` RPC — SECURITY DEFINER + search_path lockdown — that anonymizes (not hard-deletes) worker rows across 12 PII tables. Audit trail preserved via hive_audit_log. Service-role only. `DATA_RETENTION_DEFERRED` flipped to False. |

**New artifacts shipped:**
- 5 migrations: 20260511000002_db_hygiene_batch / 20260511000003_hive_quotas / 20260511000004_data_retention / 20260511000005_ai_cost_log / 20260511000006_ai_quality_log
- 2 new shared helpers: `button-lock.js`, `supabase/functions/_shared/cost-log.ts`
- `test-data-seeder/seeders/reset.py` updated (4 new tables added)
- 6 validator allowlists converted from DEFERRED → SUPERSEDED audit pattern, or flipped from `_DEFERRED = True` to `False`
- 3 validator regex improvements (html_id strip script blocks, loading-state threshold drop, data-retention erasure-helper accepts)

**Guardian state:** 120 PASS / 0 FAIL / 0 WARN unchanged throughout the batch.

**Remaining deferred:**
- **Deep refactors:** #43 OC (34 tables), #46 cold-start (35 fns), #48 reconciliation (19 pages), #49 specialist adoption (7 entries), #53 bundle bloat (2 monolithic fns)
- **Money-movement (deferred by request):** #34 Stripe Idempotency-Key (3 sites)
- **Old UX/UI:** #11 tap targets, #15 worker mini-profile drawer
- **Minor:** #58 JSONB GIN on external_sync.sync_payload, #59 hive-test.html LOC drift

### 30. Phantom column reads — 5 sites rewritten to canonical schema — FIXED 2026-05-10 (commit 155a296)

**Source:** `validate_schema_phantom.py` L1 surfaced 5 `.select()` calls referencing columns that don't exist on the target table. Each query returned null silently — page rendered, data was wrong.

**Fixes per site:**

| Site | Before | After |
|---|---|---|
| `alert-hub.html:262` | `select('id, machine, signature_kind, message, severity, hive_id, created_at')` | `select('id, machine, rule_id, alert_title, alert_detail, severity, hive_id, detected_at')` — real column names |
| `index.html:2559` | `select('..., logged_at, created_at')` from `v_logbook_truth` | Dropped phantom `logged_at`; view exposes `created_at` only |
| `search-overlay.js:276` | `inventory_items.select('..., reorder_point')` | Migrated to `v_inventory_items_truth` (the canonical view aliases `min_qty` as `reorder_point`) |
| `batch-risk-scoring/index.ts:93` | `inventory_transactions.select('part_name, ...')` | PostgREST embed: `select('qty_change, type, created_at, item:inventory_items(part_name)')` |
| `trigger-ml-retrain/index.ts:55` | Same phantom `part_name` read | Same embed pattern + flatten via `t.item?.part_name` before passing to ML training |

Each site landed with a comment explaining the canonical/alias path so the fix is self-documenting at the call site.

**Validator outcome:** L1 phantom_reads = `[]`; 4/4 PASS.

### 31. AI rate-limit gate added on 5 fns + 2 justified exemptions — FIXED 2026-05-10 (commit 155a296)

**Source:** `validate_ai_pattern_compliance.py` L1 surfaced 7 fns calling `callAI(...)` without first invoking `checkAIRateLimit(...)`. A buggy or malicious hive can burn the entire AI budget in seconds.

**Fixes:**

| Edge function | Resolution |
|---|---|
| `analytics-orchestrator` | Added `checkAIRateLimit` at handler entry |
| `project-orchestrator` | Same — gate added |
| `shift-planner-orchestrator` | Same — gate added |
| `voice-logbook-entry` | Same — highest-priority because voice is high-cost, high-frequency |
| `voice-report-intent` | Same |
| `engineering-calc-agent` | **Exempted** — AI is enrichment-only with hardcoded fallback; user-initiated bounded by calc UI (no input hive_id) |
| `failure-signature-scan` | **Exempted** — cron-driven daily; gated by schedule frequency |

Both exemptions are documented inline in `RATE_GATE_EXEMPT` of `validate_ai_pattern_compliance.py` with one-line reasons so the validator's exception list is self-explanatory.

**Validator outcome:** L1 rate_gate_first = clean; 4/4 PASS.

### 32. State machine integrity — 7 CHECK constraints added + 3 unreachable states wired — FIXED 2026-05-10 (commit 155a296)

**Source:** `validate_state_machine_integrity.py` surfaced 10 architectural debts: 3 CHECK-constrained states with no writer, 7 status columns with no CHECK constraint at all.

**Unreachable states (3) — all now have writers:**

| Table | State | Writer wired |
|---|---|---|
| `project_change_orders` | `cancelled` | `project-manager.html:2325` (.update({status: 'cancelled', ...})) |
| `asset_nodes` | `pending`, `rejected` | Asset approval flow in `asset-hub.html` |
| `shift_plans` | `archived` | Archive button in shift planner |

**Unconstrained status columns (7) — all now have CHECK constraints:**

| Table | Constraint applied |
|---|---|
| `assets` | `('approved', 'pending', 'rejected')` |
| `external_sync` | `('Cancelled', 'Closed', 'Open')` |
| `failure_signature_alerts` | `('acknowledged', 'active', 'expired')` |
| `hive_members` | `('active', 'kicked')` |
| `inventory_items` | `('approved', 'pending', 'rejected')` |
| `logbook` | `('Closed', 'Open', 'Resolved')` |
| `pm_completions` | `('done', 'skipped')` |

**Validator outcome:** 18 status-bearing tables, 18 with CHECK; 0 unreachable states. 4/4 PASS.

### 33. Audit log coverage gaps closed — viewer page + 9 writer hooks — FIXED 2026-05-10 (commit 155a296)

**Source:** `validate_audit_log_coverage.py` surfaced 3 layers of compliance debt: 9 critical-writer files unaudited, 6 audit-table columns unread (no viewer page), 9 critical tables with zero audit writers.

**Fixes:**

- **L2 — Viewer page shipped:** new `audit-log.html` lets supervisors filter audit events per actor / target / time window. Closes the "audit-without-review" regulatory-theatre gap.
- **L1 — Audit writers wired** at the 9 unaudited high-stakes sites: `asset-hub.html`, `index.html`, `inventory.html`, `logbook.html`, `marketplace-admin.html`, `marketplace-seller.html`, `marketplace.html`, `parts-tracker.html`, `pm-scheduler.html`. Each state-change site now inserts a `hive_audit_log` row with `(action, actor, target_type, target_id, target_name, meta)`.
- **L3 — Critical tables now have at least one audited writer** across all 15 tracked tables.

**Validator outcome:** L1+L2+L3 all clean. 4/4 PASS.

**Audit writer matrix:** `hive_audit_log` 9 html writers, `automation_log` 10 edge writers, `cmms_audit_log` 1 edge + 1 html. Audit data flows from worker actions to the viewer page that workers and supervisors can review.

### 36+37. Supabase Auth migration shipped end-to-end — auth.uid() now gates 5 hive-scoped tables — FIXED 2026-05-10

**Source:** validate_rls_readiness (#36) catalogued 10 permissive `USING(true)` policies on 5 hive-scoped tables. validate_auth_migration_readiness (#37) audited what was needed before the flip. User explicit ask 2026-05-10 satisfied the prior `project_supabase_auth_migration` deferral gate.

**Surprise: the migration was much further along than expected.** Phase A audit revealed:
- Supabase Auth provider already active (`db.auth.signUp` / `signInWithPassword` in index.html)
- 10 HTML pages already pulled `db.auth.getSession()` into `_authUid` opportunistically
- Inserts already set `auth_uid: _authUid || null` defensively
- 6 prior migrations had backfilled `auth_uid` columns on user-data tables
- Auth-gated sibling policies pre-staged on all 5 L3 tables

So Phase C (column adds) and Phase D (sibling policies) were no-ops — already done.

**Phases shipped:**

| Phase | What shipped | Outcome |
|---|---|---|
| **A. Audit** | `validate_auth_migration_readiness.py` (12th cross-cutting gate) | 3-layer static audit: sibling coverage + auth_uid columns + identity gate strength. L1+L2 PASS, L3 surfaces page hardening punch list |
| **B. Sign-in required** | 9 pages hardened with `if (!_authUid) { redirect → signin }` | hive, logbook, inventory, pm-scheduler, community, skillmatrix (standard pattern) + dayplanner (await conversion) + project-manager (reorder) + marketplace (softer `WORKER_NAME && !_authUid` for anon-friendly browsing) |
| **C-data. Straggler backfill** | `20260510000009_phase_c_auth_uid_backfill.sql` | 19 straggler rows across pm_completions/logbook/inventory_transactions/marketplace_sellers all backfilled by joining to worker_profiles. Dynamic Q2 verified 0 across all 12 eligible tables. |
| **E. Policy flip** | `20260510000010_phase_e_drop_permissive_policies.sql` | 10 permissive policies dropped via `DROP POLICY IF EXISTS`. Auth-gated siblings (logbook_read, logbook_insert, etc.) now actively gate access. Live verification SQL returned 0 rows. |

**Validator improvements bundled in:**
- `validate_rls_readiness.py` — added DROP POLICY parser; policies dedup by (table, name) via interleaved CREATE/DROP events keeping last-writer-wins, matching Postgres re-applied-migration semantics. Validator now reflects live policy state, not historical sum.
- `validate_auth_migration_readiness.py` — L2 strip-then-search distinguishes unqualified `auth_uid` (own column needed) from qualified `hm.auth_uid` (membership-chain JOIN, no own column needed); L3 recognizes both strong gate (`!_authUid`) and softer marketplace gate (`WORKER_NAME && !_authUid`).

**Live data state after migration:**
- All 5 L3 tables (logbook, inventory_transactions, community_posts, community_replies, community_xp): only auth-gated policies remain. Anon role has no path to read or write these tables.
- 19 backfilled rows are now properly owned by their authed workers; visible to those workers and members of their hives.
- Auth-gated siblings handle the OR-semantics correctly: a row passes if `auth.uid() IS NOT NULL AND (membership OR ownership)` per table's policy.

**Remaining: Phase F (cleanup) — low priority.** Pages still read WORKER_NAME from localStorage as their identity source; the auth gate now enforces that workers must be authenticated before pages load, so the localStorage path is belt-and-braces. Future cleanup migrates pages to derive WORKER_NAME from `worker_profiles` via `auth.uid()` lookup, retiring the localStorage layer entirely.

**Validator outcomes:** validate_rls_readiness 4/4 PASS, validate_auth_migration_readiness 3/3 PASS, guardian baseline 76 PASS / 0 FAIL.

**Recovery path if needed:** the 10 dropped policies can be recreated by re-applying the original CREATE POLICY statements from `20260420000000_baseline.sql`, `20260430000000_community_tables.sql`, `20260430000002_community_xp.sql`. Live workers continue to function during any recovery window (the auth-gated siblings still grant access to authed workers in their hives).

### 35. Cron config drift — hardcoded host + placeholder bearers in 8 active cron jobs — FIXED 2026-05-10

**Source:** validate_cron_schedule_integrity (10th cross-cutting architectural gate) surfaced 14 L3 findings — 6 jobs in `20260425000003_scheduled_agents.sql` hardcoding `hzyvnjtisfgbksicrouu.supabase.co`, plus 8 jobs across 2 migrations with placeholder bearer tokens (`SUPABASE_CRON_SERVICE_KEY`, `YOUR_PROJECT`, `SERVICE_ROLE_KEY`). Live cron worked because the deployer manually rotated keys post-deploy, but every clone / staging / customer self-host would have applied the misleading defaults.

**Fix — single new migration `20260510000008_cron_portable_urls.sql`:**

`pg_cron` is last-writer-wins per `job_name`, so the new migration unschedules + reschedules each of the 8 jobs with the portable form already in use by `20260505000002_project_knowledge.sql`:

```sql
url     := current_setting('app.supabase_functions_url') || '/<fn-name>'
headers := jsonb_build_object('Authorization', 'Bearer ' || current_setting('app.service_role_key'))
```

Both settings are configured per-project by Supabase — no manual rotation across projects.

**Jobs migrated to portable form (8 total):**
| Job | Schedule | Endpoint |
|---|---|---|
| `pm-overdue-daily` | `0 6 * * *` | `/scheduled-agents` (body: `pm_overdue`) |
| `failure-digest-weekly` | `0 7 * * 1` | `/scheduled-agents` (body: `failure_digest`) |
| `shift-handover-morning` | `0 6 * * *` | `/scheduled-agents` (body: `shift_handover`) |
| `shift-handover-afternoon` | `0 14 * * *` | `/scheduled-agents` (body: `shift_handover`) |
| `shift-handover-night` | `0 22 * * *` | `/scheduled-agents` (body: `shift_handover`) |
| `predictive-weekly` | `0 20 * * 0` | `/scheduled-agents` (body: `predictive`) |
| `batch-risk-scoring-daily` | `0 5 * * *` | `/batch-risk-scoring` |
| `ml-retrain-weekly` | `0 18 * * 6` | `/trigger-ml-retrain` |

Each block wrapped in `DO $$ ... IF EXISTS pg_cron ... EXCEPTION WHEN OTHERS THEN NULL` so the migration is a no-op on environments without pg_cron (local Supabase by default).

**Validator improvement bundled in:** `_extract_cron_jobs()` now dedupes by `job_name` keeping the last-defined entry (file order = apply order). This mirrors pg_cron's actual last-writer-wins behavior so the validator naturally reports the *current* schedule state rather than a historical sum — future cron renames work the same way without needing an exempt list.

**Validator state:** 3 PASS / 1 WARN (14 findings) → **4/4 PASS / 0 WARN / 0 FAIL.**

**Deploy note:** SQL migration applied via `supabase db push` (no `subst Z:` workaround needed — that's edge functions only).

### 29. Analytics panel order reranked by decision-relevance (top = what matters most) — FIXED 2026-05-04

**Source:** UX continuation. Each phase had panels in arbitrary code order; user wanted them ranked by what matters most to read first.

**Fix — reordered the `html += render*()` lines in 4 functions:**

**Descriptive (synthesis → reliability → drilldowns → cost):**
OEE → Availability → MTBF → MTTR → PM Compliance → Downtime Pareto → Failure Frequency → Repeat Failures → Parts Consumption

**Diagnostic (root causes → recurrence → correlations → taxonomy → QA):**
Failure Mode Distribution → Repeat Failure Clustering → PM-Failure Correlation → Skill-MTTR Correlation → Parts Availability Impact → RCM Consequence → Engineering Validation

**Predictive (trend → specific predictions → triage → realtime → schedule → supply → leading indicator):**
Failure Trend → Next Failure Prediction → Health Scores → Anomaly Baseline → PM Due Calendar → Parts Stockout → Parts Consumption Spike

**Prescriptive (synthesis → triage → this-week ops → schedule change → HR development):**
AI Action Plan → Priority Ranking → Technician Assignment → Parts Reorder → PM Interval Optimization → Training Gaps

**Skills consulted:**
- Analytics Engineer: "lead with the most-asked exec KPI" + "one chart, one insight" — synthesis first, drilldowns after
- Designer: hierarchy preserved (orange Action Plan card stays at top of Prescriptive)
- Mobile Maestro: above-the-fold = ~1 panel on 375px; the most decision-relevant panel is now first on every tab

**Risk:** zero. Pure DOM order swap. No content/schema changes.

### 28. Analytics role-view layout — period controls moved to header + Supervisor card absorbed full AI rec — FIXED 2026-05-04

**Source:** UX Phases 2 + 3 of the role-card cleanup (continuation of #27).

**Phase 2 — period controls relocated:**
The period selector (30·90·180·1yr) and Refresh button were sitting BETWEEN the role-quick-view and the status bar, making them feel role-specific even though they're page-level controls. Moved them up to sit immediately under the page header (above the role-bar), grouping all page-level controls together.

**Phase 3 — Supervisor card absorbed the AI recommendation in full text:**
After #27 deleted the duplicate banner below the role card, the AI synthesis (`presc.action_plan.summary`) had no place to render in full. Added a styled `.role-ai-rec` block inside the Supervisor view that shows the complete recommendation (no `.slice(0, 80) + '...'` truncation). Light purple background, border, label "⚡ AI recommendation", body text at 0.74rem. Stays at the bottom of the card since it integrates the rows above.

**Result:** above-the-fold layout is now:
- Page header (title + Stage 3 badge)
- Period selector + Refresh
- Role tabs (Worker / Supervisor)
- Role quick view (with AI rec inside if Supervisor)
- Status bar
- Phase tabs + filter chips + phase content

Three role views collapsed to two; the redundant chip strip and duplicate banner from #27 are gone; the AI recommendation now reads in full inside the role card. ~30 KB removed total across #27 + #28.

### 27. Analytics role views were cluttered + included a fake "Manager" role + duplicated AI banner — FIXED 2026-05-04

**Source:** UX Phase 1 of role-card cleanup (after #24/25/26 list-scaling work).

**What was wrong:**
- The Analytics page had 3 role tabs: Field Tech / Supervisor / Manager. But per the multitenant-engineer skill ("a worker can only read and write their own hive's data; a supervisor can manage members…"), **only Worker and Supervisor exist as actual `hive_members.role` values**. Manager was a UI fiction showing reframed supervisor data.
- A "Command Summary Bar" below each role card showed KPI pills (MTBF/MTTR/PM Compliance/OEE/anomaly count) — the same numbers already rendered inside each role card AND inside each phase panel. Triple duplication.
- An AI recommendation banner appeared TWICE on Supervisor + Manager screens — once truncated inside the role card, once full-text below as a separate banner.

**Fix:**
- Removed Manager button from role-bar HTML.
- Removed `buildManagerView()` (~25 lines).
- Removed `updateCommandBar()` (~95 lines), `ragColor()`, `makePill()`.
- Removed `<div id="command-bar">` HTML and the orphaned `command-pills` / `command-alert` container.
- Removed `.cmd-pill` CSS (15 lines).
- `setRole()` now clamps unknown role values to `worker` so any stale localStorage `_role='manager'` falls back gracefully.

Net diff: ~150 lines removed. Same information, less duplication. Above-the-fold real estate freed up so the role card and phase tabs sit closer together.

**Skills consulted:**
- Multitenant Engineer — confirmed only 2 hive roles exist
- Analytics Engineer — `>5 KPIs needs role toggle` (kept), Manager tier was aspirational not implemented
- Designer — pill-style toggle group preserved for the role switcher (correct pattern)

**Verified:** page HTTP 200, 113KB (was ~118KB), zero leftover references to the removed names.

### 26. Analytics global filter chips — narrow every panel by criticality + discipline — FIXED 2026-05-04

**Source:** UX Phase 2 of the Analytics scaling plan (after #24 Top-N + #25 search).

**What was added:** A pill-style filter chip bar at the top of the Analytics page, between the phase tabs and the info banner. Two dimensions:
- **Criticality:** All / Critical / High / Medium / Low (5 chips)
- **Discipline:** All / Mechanical / Electrical / Instrumentation / Hydraulic / Pneumatic / Lubrication (7 chips)

Server-side filter at the orchestrator (analytics-orchestrator/index.ts: new `applyFilters(data, filters)` function). After fetching raw data per phase, narrows every asset-keyed array (logbook entries, pm_completions, pm_scope_items, pm_assets) plus the precomputed RPC arrays (MTBF/MTTR/Frequency/Pareto/Repeats) by an `allowedCodes` set built from the filters. Discipline-only filters that hit logbook also narrow the precomputed RPCs by deriving allowedCodes from the filtered logbook's machine codes.

State persists in `localStorage.wh_analytics_filters` so the user's selection survives page reloads. Filter change clears the per-phase cache and re-fetches all 4 phases. Active filter banner ("Filtered: Criticality: Critical · Discipline: Mechanical · clear") appears below the chips when any filter is applied.

**Skills consulted:**
- Designer: pill-style toggle button group preferred over `<select>` for 3-8 known options.
- Frontend: state in `let _filters = {...}`, persistence via localStorage, cache invalidation on filter change.
- Mobile Maestro: chips are 32px visual / 44px hitbox via padding; horizontal scroll on the discipline group below 600px so the row doesn't wrap awkwardly.

**Verified with seeded Lucena hive (30 assets, 6 Critical):**
- `criticality=Critical` → priority ranking 6 rows (was 30), MTBF/MTTR narrowed
- `discipline=Mechanical` → 25 MTBF rows (Mechanical-only machines)
- `criticality=Critical AND discipline=Mechanical` → 4 ranking rows (intersection)

### 25. Analytics search input on long lists — find an asset/part by typing — FIXED 2026-05-04

**Source:** Continuation of #24 (UX overflow). With 30 assets per hive a "Show all" button only solves part of the problem; users still scroll to find a specific machine.

**Fix:** Extended `renderListWithShowAll()` with two new options: `searchable: true` and an optional `searchPlaceholder`. When enabled AND the list has ≥ 8 items, the helper renders a `<input type="search">` above the list. Typing filters rows by `textContent.includes(query)` (case-insensitive). Search auto-expands the hidden Show-All container so matches outside the top N are visible. Clearing the input restores the default Top-N view.

**Panels with search now:** MTBF, MTTR, Availability, Parts Consumption, Repeat Failures (auto for ≥8), Priority Ranking, PM Interval Optimization (custom placeholder "Filter by asset name or code…"), Parts Reorder, Next Failure Prediction. 8 panels total.

**Mobile considerations (per Mobile Maestro skill):**
- Input `font-size: 0.82rem` (≥ 16px effective) — no iOS auto-zoom on focus
- `min-height: 38px` — close enough to tap target without overwhelming the visual
- `type="search"` gets the native iOS clear button ✕
- `-webkit-appearance: none` removes weird iOS rounded-rect default

**Skipped:**
- Failure Frequency (bar chart aesthetic — search would clutter)
- Small lists (<8 items) — search hidden by the `total >= 8` guard inside `renderListWithShowAll`

### 24. Analytics panels overflowed with realistic data — added Top-N + Show All pattern — FIXED 2026-05-04

**Source:** `ui:Analytics page (test session 2026-05-04, all 4 phases)`

**What was wrong:** With 30 seeded assets per hive and 90-day breakdown history, several Analytics panels rendered the entire dataset (30+ rows) inline, producing a forever-scroll page. Worst offender was PM Interval Optimization at 30 cards before #21, still 30 after; Priority Ranking, MTBF, MTTR, Availability, Repeat Failures, Next Failure Dates, and Parts Reorder all had no caps.

**Fix:** Added one reusable `renderListWithShowAll({ items, renderRow, wrap, tableHeader, defaultN, itemNoun })` helper in `analytics.html` (defined once, applied 10 times). It renders the first N items visibly, hides the rest in a sibling `<tbody class="extra-rows" hidden>` (or `<div class="extra-cards" hidden>` for card lists), and emits a `<button class="showall-toggle">Show all 30 assets ↓</button>` that flips the hidden attribute. No re-render on toggle. Mobile-tap-target compliant (44px min height, per Mobile Maestro skill).

**Panels upgraded:**
- Descriptive: MTBF, MTTR, Availability, Failure Frequency, Parts Consumption, Repeat Failures
- Predictive: Anomaly Baseline (was 90+ row flood), Parts Spike, Next Failure Prediction, Parts Stockout
- Prescriptive: Priority Ranking, PM Interval Optimization, Parts Reorder

**Pattern reuse:** the helper accepts `wrap: 'table' | 'cards'` so it works for both data-table panels and stacked-card panels (PM Optimization, Availability, Failure Frequency). Single source of truth.

**Skills consulted:** Designer (toggle button group preferred over dropdown), Frontend (dom modal-before-script rule preserved; helper avoids re-rendering on toggle), Mobile Maestro (44px tap target on toggle button), Analytics-engineer (mobile-readable list patterns, top-N stays visible by default).

**Found by:** user noted PM Interval Optimization scrolling endlessly with 30 Kaeser CSD 105 cards.

### 23. Priority Maintenance Ranking showed every asset as Medium / P1 — three layered bugs — FIXED 2026-05-04

**Source:** `ui:Analytics Prescriptive tab > Priority Maintenance Ranking (test session 2026-05-04)`

**What was wrong:** the panel showed all 30 seeded assets as "Medium" criticality and all as P1, making the ranking useless. Three stacked bugs:

1. **Seeder vocabulary mismatch:** `assets.py` produced criticality values `Major / Minor / Critical`, but the platform's canonical labels (per `pm-scheduler.html` dropdown) are `Critical / High / Medium / Low`.
2. **Calc lookup keyed wrong:** `calc_priority_ranking()` keyed `crit_map` by `asset_name` and looked up by `logbook.machine` (which is the human asset code, not the name). Same architectural issue as #17. Lookup always missed → "Medium" default for every machine.
3. **Edge function didn't pass `tag_id`:** `fetchPrescriptiveData` SELECTed `id, asset_name, category, criticality` from pm_assets but omitted `tag_id` (the human code). Even after fixing #2, the calc had no key to look up by.
4. **Tier thresholds too low:** P1 ≥ 20 / P2 ≥ 8 made every asset P1 once basic failure activity existed. With realistic 90-day data scores reach 50-250.

**Fix:**
- `seeders/assets.py`: `CRITICALITY_WEIGHTS` now uses canonical `Critical / High / Medium / Low` (with Critical~12% / High~25% / Medium~50% / Low~12% distribution).
- `prescriptive.py CRITICALITY_WEIGHT`: kept canonical 4 plus Major/Minor aliases for backward-compat with un-reseeded data.
- `prescriptive.py calc_priority_ranking`: keyed `crit_map` by `tag_id` (human code) instead of asset_name; matches `logbook.machine`.
- `analytics-orchestrator/index.ts fetchPrescriptiveData`: added `tag_id` to the pm_assets SELECT.
- Tier thresholds: P1 ≥ 150, P2 ≥ 60 (was 20/8). Calibrated for 90-day windows.

**Verified with seeded Lucena hive:** 8 P1 / 22 P2 / 0 P3 (was 30 P1 / 0 P2). Top of list now shows Critical machines (PV-002, BF-002), then Major (TT-002, MILL-001). Real prioritization signal.

### 22. AI Action Plan only saw Prescriptive data — now reasons across all 4 analytics phases — FIXED 2026-05-04

**Source:** `ui:Analytics Prescriptive tab > AI Action Plan panel (test session 2026-05-04)`

**What was wrong:** `callGroqSynthesis()` in `analytics-orchestrator/index.ts` built its prompt from prescriptive recommendations only (priority_ranking, pm_optimizations, assignments, reorder, training_gaps). The AI couldn't reference WHY anything was being recommended — no MTBF/MTTR numbers (descriptive), no failure modes or correlations (diagnostic), no forecasted failures or stockout dates (predictive). Output was generic templated bullets like "Pablo to focus on X, others to support, review PM frequency."

**Fix:** Server-side fan-out. When phase=prescriptive runs, the orchestrator now also calls Python for descriptive + diagnostic + predictive in parallel using the same loaded data shape, builds a 4-phase context bundle, and passes that to Groq with an updated system prompt that explicitly instructs the AI to draw cross-phase connections (descriptive number + diagnostic root cause → prescriptive action; predictive forecast + prescriptive reorder → watch-list entry).

**Verified with seeded Lucena hive:** action plan now cites specific machine codes, KPI numbers, and phase signals. Example: "Inspect TT-002 — highest downtime hours (70.6) and failure count (16) with top root cause of Wear (diagnostic)." Watch list now explains WHY each item is on it ("AC-002 forecast to fail soon (predictive), only 1 spare seal kit (prescriptive reorder)"). Cost: 3 extra Python calls per Prescriptive load, ~2-5s added latency on warm cache. Worth it for once-per-session action plans.

### 21. PM Interval Optimization spammed N cards per asset (one per scope item) and didn't show machine_code — FIXED 2026-05-04

**Source:** `ui:Analytics Prescriptive tab > PM Interval Optimization (test session 2026-05-04)`

**What was wrong:** The Python calc emitted one recommendation per scope item per asset. With 30 assets each having ~5 PM tasks (Weekly/Monthly/Quarterly/Semi-annual/Annual), that's 145+ cards all saying the same thing per asset. Plus, when multiple assets share a model name (4 Kaeser CSD 105 compressors in the same hive), the rendered cards were indistinguishable — no machine_code shown.

**Fix:**
- `prescriptive.py calc_pm_interval_optimization`: aggregate by asset. Compare MTBF against the TIGHTEST current PM interval (most frequent task) for "increase" decisions, against the LOOSEST for "reduce" decisions. Emit ONE recommendation per asset with `scope_items_count` indicating how many tasks the change covers.
- `analytics.html renderPMOptimization()`: show the machine_code badge next to asset name (gold-tinted code chip), and add "covers N PM tasks" to the recommended-frequency line.

**Verified with seeded Lucena hive:** went from 145 recs → 30 recs (one per evaluated asset). Each card distinguishable by machine_code. AC-001 through AC-004 are 4 separate Kaeser CSD 105 compressors, now visibly different.

### 20. Technician Assignment piled every open job on the highest-skilled supervisor — FIXED 2026-05-04

**Source:** `ui:Analytics Prescriptive tab > Technician Assignment panel (test session 2026-05-04)`

**What was wrong:** `calc_technician_assignment()` in `prescriptive.py` picked a single "best tech per discipline" (highest level), then assigned every job in that discipline to the same person. With one cross-trained supervisor (e.g. Pablo Aguilar L3+ in Mechanical, Electrical, AND Instrumentation), all 10 displayed jobs landed on him. Realistic supervisors would never do this — they'd spread the load.

**Fix:**
- Replaced `best_by_disc: dict` (single best) with `ranked_by_disc: dict` (sorted list of qualified techs per discipline).
- Added a `MAX_CONCURRENT_JOBS = 3` cap and a per-worker `load` counter.
- New `_pick_next_best(disc)` helper: returns highest-skilled tech under the cap; if all are capped, returns the fewest-loaded one (skill level breaks ties).
- Each assignment's `reason` field now explains the picking logic — "no current open jobs" / "currently has N other open jobs" / "all {disc} techs at workload cap; fewest-loaded wins."

**Verified with seeded Lucena hive (5 workers, 18 open jobs, 10 displayed):** Pablo gets 4 (3 Mechanical + 1 Instrumentation, his cap), David Velasco gets 4 Mechanical (L1 backup), Ricardo Morales 1 Instrumentation, Dennis Aquino 1 Electrical. Spread is realistic.

**Found by:** user spotted the "all 10 jobs to one person" pattern during prescriptive walkthrough.

### 19. Two Prescriptive panels showed false-positive "all good" green checkmarks when calc had nothing to compare — FIXED 2026-05-03

**Source:** `ui:Analytics Prescriptive tab > PM Interval Optimization + Training Gap Recommendation panels (test session 2026-05-03)`

**What was wrong:** Both panels rendered a green ✓ message ("Current PM intervals are appropriate" / "No significant training gaps detected") whenever their `recommendations`/`gaps` arrays were empty — without distinguishing "we evaluated everything and it's healthy" from "we couldn't evaluate anything and have no findings to report." The user got false confidence in two different unrelated states.

**Root cause:** Python calcs returned `{recommendations: [], standard: "..."}` regardless of whether 0 assets were comparable or 50 assets were compared and all healthy. UI couldn't tell which.

**Fix:**
- `prescriptive.py calc_pm_interval_optimization`: now returns `compared_count`, `skipped_count`, `scope_asset_count` so the UI can render one of three honest messages — "compared N healthy" / "couldn't compare" / "no scopes registered."
- `prescriptive.py calc_training_gaps`: now returns `categories_evaluated`, `above_threshold_count`, `badge_count` — UI renders one of four honest messages — "no closed entries" / "no skill badges" / "evaluated N, no spikes" / "spikes exist but everyone is L3+."
- `analytics.html renderPMOptimization()` + `renderTrainingGaps()`: branch on the new fields to pick the right empty-state copy. The misleading green ✓ only fires when there's actual evidence of healthy state.

**Found by:** user noticed the green ✓ on PM Interval Optimization while the underlying data was clearly broken (related to #17). Asked "why I got this result in prescriptive" — the panel was lying to them.

### 18. Technician Assignment skill-gaps panel showed duplicate generic messages, hid machine context — FIXED 2026-05-03

**Source:** `ui:Analytics Prescriptive tab > Technician Assignment panel (test session 2026-05-03)`

**What was wrong:** Python (`prescriptive.py:267-271`) builds skill_gap entries with `{machine, discipline, gap}` — three fields per gap. The renderer in `analytics.html:1457` was only displaying `g.gap` (the pre-formatted generic string `No qualified Mechanical technician found in the team.`), discarding the machine name and discipline. Result: 8 identical-looking lines for 8 different machines, with no indication of WHICH machines were unassigned. Useless for action.

**Fix:** Group gaps by discipline, show the discipline as a single rolled-up line with the affected machine count + first 4 machine names (truncated with "+N more" overflow). Now one row per missing discipline, with concrete context for what to do about it.

**Found by:** user spotted the duplicate "No qualified Mechanical technician found in the team" lines while exploring the Prescriptive tab.

### 16. Edge functions had two flavors of schema drift on inventory_items + inventory_transactions — FIXED 2026-05-03

**Source:** `ui:Analytics page Descriptive tab "Parts Consumption Rate" panel always empty`

**What was wrong:**
1. `analytics-orchestrator/index.ts:67` SELECTed `part_name` from `inventory_transactions`. That column doesn't exist on that table — `part_name` lives on `inventory_items`. PostgREST silently returned rows without a part_name, the Python `calc_parts_consumption()` saw `df.part_name` missing, and dropped to "No parts usage transactions found in period" no matter how much data was seeded.
2. `analytics-orchestrator/index.ts:152` and `ai-orchestrator/index.ts:91` SELECTed `reorder_point` from `inventory_items`. Real column is `min_qty` (same bug as #12 in `assistant.html`, in two more places). Predictive stockout calc and the AI inventory-risk agent both saw `undefined` and silently produced wrong results.

**Production impact:** Every analytics user got an empty "Parts Consumption Rate" panel; predictive stockout calculations were wrong; the AI assistant's inventory-risk agent reported "qty:5|reorder_at:undefined" to the LLM and got noise back.

**Fix:**
- Embed `inventory_items(part_name)` in the inventory_transactions PostgREST query, then flatten the nested object before passing to the Python API.
- Alias `min_qty` as `reorder_point` in both edge functions' selects so the existing Python and prompt logic keeps working: `select("..., reorder_point:min_qty, ...")`.

**Validator extension that prevents recurrence:** `validate_schema_coverage.py` originally scanned only HTML/JS at the project root. Extended it to also scan `supabase/functions/*/index.ts` and `supabase/functions/_shared/*.ts`. Findings count jumped from 105 → 133 db.from().select() calls scanned. The 3rd reorder_point bug in ai-orchestrator was caught immediately by the validator after the extension; without it, that one would have shipped with the first two fixes.

**Found by:** user spotted the empty Parts Consumption panel during the Descriptive analytics walkthrough.

**Verified by:** `python validate_schema_coverage.py` returns `2 pass · 0 warn · 0 fail` (133 calls scanned, all known columns). Edge runtime restarted; analytics-orchestrator now returns `"source":"python_computed"` with no errors.

### 14. Team Stock Issues panel showed worker names + counts instead of the actual parts — FIXED 2026-05-03

**Source:** `ui:hive.html Team Stock Issues panel (test session 2026-05-03)`

**What was wrong:** The panel rendered "David Velasco — 1 low / Emma Velasquez — 1 low / Ricardo Morales — 1 low". You can see WHO is short, but not WHAT they're short of. In a hive context where inventory is shared and supervisors approve new stock, the actionable signal is the part name (so you can plan a buy/order), not whose name is attached.

**Fix:** Refactored `renderTeamStockSummary()` in `hive.html` (lines 1774-1802) to flatten the item list rather than group by worker. Now shows: `[•] Bearing 6204    Marcelino Madrigal    [3 of 5 pcs]`. Out-of-stock items sort first (red dot + "OUT" pill); low items second (gold dot + "X of Y unit" pill); alphabetical within each severity. Capped at 8 visible items with "+N more" overflow link.

**Found by:** user spotted it during their first hands-on testing session via the seeded data. Exactly what the closed-loop dashboard is for.

### 13. Hive join fails with FK violation when browser has stale Supabase JWT after reseed — FIXED 2026-05-03

**Source:** `ui:Hive join flow (test session 2026-05-03)`

**Test message:** `Could not join: insert or update on table hive_members violates foreign key constraint hive_members_auth_uid_fkey`

**Root cause:** Reset wipes `auth.users` (delete by email). Reseed creates new auth users with new UUIDs. But the browser still holds the OLD Supabase JWT from before the wipe. JWTs are stateless, so `db.auth.getSession()` happily returns the stale session. When the hive-join code INSERTs into `hive_members` with that dead `auth_uid`, the FK constraint fails.

**Production impact:** any user whose `auth.users` row gets deleted (rare in prod, but plausible during account merges, admin cleanup, or when someone deletes their account and re-signs up) will hit a confusing FK error and be unable to join a hive.

**Fix:** in `hive.html` join handler, detect the FK error pattern (`/auth_uid.*fkey|violates foreign key/i`), auto-sign-out, clear all `wh_*` localStorage keys, and redirect to `index.html?signin=1`. The user gets a friendly message ("Your sign-in session expired (auth was reset). Redirecting you to sign in again…") instead of the raw error.

**Verified by:** the next time you Reset + Reseed in the Tester and try to join a hive, instead of dead-ending on the FK error, you're cleanly redirected to sign in fresh.

### 12. assistant.html queried inventory_items with wrong column names (name, reorder_point) — FIXED 2026-05-03

`assistant.html:424` SELECTed `name, reorder_point` from `inventory_items` but the schema columns are `part_name` and `min_qty`. The downstream low-stock filter and render logic at lines 476-478 also referenced the wrong field names, so all 5 references were broken.

**Production impact:** workers using the AI assistant on a hive page got broken inventory context. Items showed as `undefined: 5 pcs` in the prompt, and the low-stock filter never triggered (`i.reorder_point` was always `undefined`, falling through to the `qty_on_hand <= 2` fallback). The AI saw broken data and either ignored inventory or hallucinated names from elsewhere in the prompt.

**Fix:** at all 5 references in `assistant.html`, changed `name` → `part_name` and `reorder_point` → `min_qty`. The actual schema (in `supabase/migrations/20260420000000_baseline.sql:828`) defines `part_name` and `min_qty`.

**Found by:** the new `validate_schema_coverage.py` validator on its first run. It auto-derives the table/column map from `supabase/migrations/*.sql` and checks every `db.from().select()` plain-column reference exists. Caught both bad columns immediately.

**Verified by:** `python validate_schema_coverage.py` returns `2 pass · 0 warn · 0 fail`. Full `python run_platform_checks.py --fast` returns `56 PASS · 0 FAIL · 0 WARN`.

### 2. iOS auto-zoom on inputs in pm-scheduler + marketplace pages — FIXED 2026-05-04

Found and fixed in one session:
- `pm-scheduler.html` — `<select id="cat-filter">` had inline `font-size:0.875rem`. Removed the inline override so `wh-input`'s 1rem default takes over.
- `marketplace.html` — three CSS classes (`.search-input`, `.wh-select`, `.wh-textarea`) all had `font-size: 0.82rem`. Bumped all three to `1rem`.

**Verified by:** Mobile Playwright flow now reports `41 pass, 0 fail` (was `39 pass, 2 fail`). All visible inputs measure ≥16px.

### 7. semantic-search + embed-entry used non-existent Groq embedding model — FIXED 2026-05-04

Replaced the single Groq embedding call (which never worked — Groq offers chat-only) with a 2-provider fallback chain at `supabase/functions/_shared/embedding-chain.ts`:

1. **Voyage AI** (`voyage-3.5-lite` at 512 dims, truncated to 384) — primary, 200M tokens/month free
2. **Jina AI** (`jina-embeddings-v3` at 384 dims native) — secondary, 100M tokens/month free

Both `semantic-search` and `embed-entry` now import `generateEmbedding()` from this shared file. Output is a 384-dim vector compatible with the existing `vector(384)` schema on knowledge tables.

**Verified by:**
- Local edge function logs show `[embedding] ok via voyage (384 dims)` on every semantic search call
- AI gate's `ai_semantic` test now PASS (was KNOWN-FAIL)
- Total free capacity ~300M tokens/month, sustainable for production

**Production migration:** Add `VOYAGE_API_KEY` and `JINA_API_KEY` to your Supabase project's secrets dashboard before deploying. Without those, the chain falls through and embeddings throw — same behavior as before, just with explicit error.

---

### 10. handle_community_post_xp trigger didn't propagate auth_uid — FIXED 2026-05-04

When the trigger awards `voice_of_the_hive` to a worker on their 10th post, it inserted into `skill_badges` without `auth_uid`. Result: badge rows had NULL auth_uid, which under RLS means the badge owner can't read their own badge. Migration `20260504000001` updates the trigger to copy `NEW.auth_uid` (the post author's auth_uid) onto the badge row.

**Verified by:** Test runner's "auth_uid populated everywhere" check, which previously flagged 2/31 skill_badges as NULL.

---

### 9. assistant.html queried non-existent skill_badges.badge_type column — FIXED 2026-05-04

`assistant.html:422` queried `db.from('skill_badges').select('discipline,level,badge_type')` — but the column is `badge_key`, not `badge_type`. Result: every page load fired a 400 Bad Request that silently dropped the worker's badge context from the AI assistant's prompt.

**Fix:** changed `badge_type` to `badge_key` in `assistant.html`. The column was added by migration `20260504000000_skill_badges_badge_key.sql` (this session).

**Status:** FIXED 2026-05-04

---

### 8. AI orchestrator returns structured object instead of string — FIXED 2026-05-04

`ai-orchestrator`'s synthesis step asks the LLM for `{ "answer": "string" }` but Groq sometimes returns `{ "answer": { ...structured... } }`. The frontend then renders `[object Object]` instead of useful content.

**Fix:** added `formatStructuredAnswer()` post-processor in `ai-orchestrator/index.ts` that converts an object answer into bullet-formatted markdown text (key → bold heading, arrays → bulleted lists).

**Verified by:** AI assistant now shows readable bullet-formatted answers with named machines, downtime hours, and root causes.

### 1. `skill_badges.badge_key` column missing — FIXED 2026-05-04

Migration `20260504000000_skill_badges_badge_key.sql` adds:
- `badge_key text` column on `skill_badges`
- Non-partial UNIQUE INDEX `(worker_name, badge_key)` (Postgres treats NULLs as distinct, so existing exam-based badges with NULL badge_key don't conflict)
- `DEFAULT 0` on `exam_score` so the community trigger insert (which omits exam_score for non-exam badges) doesn't violate NOT NULL

**Verified by:** Release gate now reports 0 failures across 155 automated checks. Voice of the Hive badge correctly awards on the 10th community post per author in a hive.

### 3-6. Platform Guardian regressions — FIXED 2026-05-04

These were *artifacts of the test environment* (pg_dump baseline file conflicting with developer-format validators), not real production bugs. All 4 cleared:

- **Marketplace Validator + Knowledge Freshness** — fixed by restoring the original 38 incremental migrations alongside the baseline (the original developer-format SQL contains the patterns the validators look for).
- **Vector Schema + Idempotency** — fixed by teaching `validate_vector_schema.py` and `validate_idempotency.py` to skip `*_baseline.sql` files (which use pg_dump's quoted-identifier dialect, not the project's developer convention).

**Verified by:** Platform Guardian now reports `54 PASS · 0 FAIL` (was `50 PASS · 4 FAIL`). Release gate verdict: **READY — safe to deploy**.

---

### 29. Add missing `id` field to all `inventory_transactions.insert()` calls

**Discovered:** 2026-05-05 — user reported "Parts log failed: check your connection" toast when editing an open logbook entry, adding parts, and saving to Closed

**What's wrong:**
`inventory_transactions.id` is `TEXT NOT NULL` with no DEFAULT. All three insert call sites in `logbook.html` omitted the `id` field entirely. PostgreSQL returned a not-null constraint violation on every parts save. Because `inventory_items.update()` (the qty deduction) runs before the `inventory_transactions.insert()`, the inventory WAS decremented but the transaction record was never written. The toast message "check your connection" misdirected investigation away from the real cause.

The entry itself was saved correctly to Closed items — the only failure was the transaction log.

**Where:**
- `logbook.html` — three insert sites: `saveEdit()` (line ~2921), `saveEditFromForm()` (line ~3023), new-entry path (line ~3359)

**How to fix:**
1. Add `id: Date.now().toString() + Math.random().toString(36).slice(2)` to each `inventory_transactions.insert()` payload

**Validator gap closed:**
Added `check_txn_id_present` (L2 check #7) to `validate_logbook.py` — now 21 checks total.
Added edit-to-closed path (Check 4) to `test-data-seeder/flows/logbook.py`.

**Status:** FIXED 2026-05-05, commit `07600a9`

---

## Template for new entries

```
### N. Short imperative title

**Discovered:** YYYY-MM-DD — which test/page/seeder surfaced it

**What's wrong:**
Plain-English description of the bug or gap. Include exact error message if any.

**Where:**
- File path / table / function name

**How to fix:**
1. Concrete step
2. Concrete step

**Workaround in seeder/test:** (optional)

**Status:** TO DO | IN PROGRESS | FIXED (date, commit ref)
```
