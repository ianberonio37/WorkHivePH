# Production Fixes — Discovered During Testing

Bugs, missing fields, schema gaps, and UX issues found while running the test-data-seeder against a local copy of WorkHive. Each entry has severity, location in the codebase, and how to fix.

**How to use this file:**
- Items get added here as testing surfaces them.
- Move entries between sections (🔴 → 🟡 → ✅) as priorities shift or fixes ship.
- When you ship a fix in production, copy the entry into your PR description and move it to ✅ Fixed with the date + commit ref.

**Last updated:** 2026-05-03 (entry #12 logged + fixed)

---

## 🔴 Critical — breaks a user flow

_(none currently)_

---

## 🟡 Important — degrades UX or data quality

### 8. AI orchestrator returns object instead of string for some queries — FIXED 2026-05-04

(See "Fixed" section.)

---

## 🟡 Important — degrades UX or data quality

_(none currently)_

---

## 🟢 Nice to have — polish, refactors, doc gaps

### 11. 6 tap targets <44px — OPEN 2026-05-03

**Source:** `ui:Mobile`

**Test message:** logbook.html: 6 tap targets <44px

**Found:** 2026-05-03T08:59:43+00:00 via WorkHive Tester


---

## ✅ Fixed — for the changelog

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
