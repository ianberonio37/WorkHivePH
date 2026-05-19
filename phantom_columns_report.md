# Phantom Column Audit (Layer -1.5 schema-bloat detector)

Every column in canonical_registry.json with ZERO downstream consumers.
Run by `tools/audit_phantom_columns.py`. Output is a `DROP COLUMN`
candidates punch list. Allowlist a column by adding it to
`PHANTOM_COLUMN_ALLOW` in the auditor source with a reason.

## Summary

- Tables scanned:           **124**
- Total columns:            **1331**
- Alive (consumed):         **1003** ✅
- Universal-skipped:        **316** (id, created_at, hive_id, ...)
- Allowlisted phantoms:     **0**
- Phantom (deletion cand):  **12** ❌

## Tables with phantom columns (8)

| Table | Phantom cols | Phantom column names |
|---|---:|---|
| `hive_adoption_score` | 3 | `supervisor_decay_risk`, `stair_stall_risk`, `new_worker_silence_risk` |
| `industry_standards` | 3 | `current_version`, `effective_year`, `planned_review_at` |
| `agent_memory` | 1 | `turn_text` |
| `hive_route_calls` | 1 | `hour_bucket` |
| `hive_route_quotas` | 1 | `hourly_cap` |
| `kb_chunks` | 1 | `relevance_score` |
| `platform_feedback_votes` | 1 | `voter_token` |
| `rcm_strategies` | 1 | `weibull_fit_id` |

## What to do with a phantom column

1. **DROP it** — write a follow-up migration `ALTER TABLE T DROP COLUMN c;`. Safe move.
2. **Justify it** — add an entry to `PHANTOM_COLUMN_ALLOW` in the auditor source
   with a one-line reason (external system, archival, trigger-only).
3. **Wire a consumer** — if the column should be read by a surface or edge fn,
   add the read site. The next run reclassifies as alive.