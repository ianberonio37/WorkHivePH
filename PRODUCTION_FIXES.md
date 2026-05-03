# Production Fixes — Discovered During Testing

Bugs, missing fields, schema gaps, and UX issues found while running the test-data-seeder against a local copy of WorkHive. Each entry has severity, location in the codebase, and how to fix.

**How to use this file:**
- Items get added here as testing surfaces them.
- Move entries between sections (🔴 → 🟡 → ✅) as priorities shift or fixes ship.
- When you ship a fix in production, copy the entry into your PR description and move it to ✅ Fixed with the date + commit ref.

**Last updated:** 2026-05-03

---

## 🔴 Critical — breaks a user flow

### 7. `semantic-search` and `embed-entry` use a non-existent Groq embedding model

**Discovered:** 2026-05-04 — testing AI Assistant with seeded data.

**What's wrong:**
Both `supabase/functions/semantic-search/index.ts` and `supabase/functions/embed-entry/index.ts` call Groq's embeddings API:
```typescript
fetch("https://api.groq.com/openai/v1/embeddings", {
  body: JSON.stringify({ model: "nomic-embed-text-v1_5", input: text })
});
```
**Groq does not offer embeddings** — it's a chat-completion-only API. Calling this endpoint returns:
> `Groq embedding error 404: The model 'nomic-embed-text-v1_5' does not exist or you do not have access to it.`

This means:
- New logbook/PM/skill entries are NEVER getting embedded
- The `*_knowledge` tables exist with the `embedding vector(384)` schema, but rows have `embedding = NULL`
- The AI assistant's RAG retrieval always returns "no semantic context found"
- The `search_all_knowledge` function correctly filters `embedding IS NOT NULL`, so it returns zero results

**Where:**
- `supabase/functions/semantic-search/index.ts` — uses Groq embeddings
- `supabase/functions/embed-entry/index.ts` — uses Groq embeddings
- Possibly other functions that call `generateEmbedding()`

**How to fix:** Swap to a real embedding provider:
- **Option A (recommended): Hugging Face Inference API** — has `nomic-embed-text-v1.5` for free, well-supported, OpenAI-compatible payload. Endpoint: `https://api-inference.huggingface.co/models/nomic-ai/nomic-embed-text-v1.5`
- **Option B: Cohere** — `embed-english-light-v3.0` is free up to 100 calls/min. Different API shape.
- **Option C: OpenAI** — `text-embedding-3-small` is paid (~$0.02 per 1M tokens) but most reliable.

Whichever you pick, also change the **vector dimension** in:
- `embed-entry/index.ts` — output dimension
- `semantic-search/index.ts` — query dimension
- Migration that defines `embedding vector(N)` columns — must match

If you swap from `nomic-embed-text-v1.5` (384) to `text-embedding-3-small` (1536), all knowledge tables need ALTER TABLE to widen the column.

**Production impact:** RAG-based features (assistant context, "find similar issues", knowledge surfacing in BOM/SOW prompts) all fall back to "no context found." The platform still works, just less intelligently than designed.

**Status:** TO DO — high priority, blocks the platform's "smart" features

---

## 🟡 Important — degrades UX or data quality

### 8. AI orchestrator returns object instead of string for some queries — FIXED 2026-05-04

(See "Fixed" section.)

---

## 🟡 Important — degrades UX or data quality

_(none currently)_

---

## 🟢 Nice to have — polish, refactors, doc gaps

_(none currently)_

---

## ✅ Fixed — for the changelog

### 2. iOS auto-zoom on inputs in pm-scheduler + marketplace pages — FIXED 2026-05-04

Found and fixed in one session:
- `pm-scheduler.html` — `<select id="cat-filter">` had inline `font-size:0.875rem`. Removed the inline override so `wh-input`'s 1rem default takes over.
- `marketplace.html` — three CSS classes (`.search-input`, `.wh-select`, `.wh-textarea`) all had `font-size: 0.82rem`. Bumped all three to `1rem`.

**Verified by:** Mobile Playwright flow now reports `41 pass, 0 fail` (was `39 pass, 2 fail`). All visible inputs measure ≥16px.

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
