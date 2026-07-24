# Phantom Column Audit (Layer -1.5 schema-bloat detector)

Every column in canonical_registry.json with ZERO downstream consumers.
Run by `tools/audit_phantom_columns.py`. Output is a `DROP COLUMN`
candidates punch list. Allowlist a column by adding it to
`PHANTOM_COLUMN_ALLOW` in the auditor source with a reason.

## Summary

- Tables scanned:           **156**
- Total columns:            **1624**
- Alive (consumed):         **1228** ✅
- Universal-skipped:        **396** (id, created_at, hive_id, ...)
- Allowlisted phantoms:     **0**
- Phantom (deletion cand):  **0** ❌

## Tables with phantom columns (0)

_None — every non-universal column has at least one consumer._

## What to do with a phantom column

1. **DROP it** — write a follow-up migration `ALTER TABLE T DROP COLUMN c;`. Safe move.
2. **Justify it** — add an entry to `PHANTOM_COLUMN_ALLOW` in the auditor source
   with a one-line reason (external system, archival, trigger-only).
3. **Wire a consumer** — if the column should be read by a surface or edge fn,
   add the read site. The next run reclassifies as alive.