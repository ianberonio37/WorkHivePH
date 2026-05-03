# Production Fixes — Discovered During Testing

Bugs, missing fields, schema gaps, and UX issues found while running the test-data-seeder against a local copy of WorkHive. Each entry has severity, location in the codebase, and how to fix.

**How to use this file:**
- Items get added here as testing surfaces them.
- Move entries between sections (🔴 → 🟡 → ✅) as priorities shift or fixes ship.
- When you ship a fix in production, copy the entry into your PR description and move it to ✅ Fixed with the date + commit ref.

**Last updated:** 2026-05-03

---

## 🔴 Critical — breaks a user flow

_(none currently)_

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
