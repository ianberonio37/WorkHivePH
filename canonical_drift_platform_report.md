# Canonical Drift — Platform-Wide (Layer -1.5)

Every HTML page + shared JS scanned for `.from('T').select(...)` calls.
Drift on a **user-facing KPI page** (e.g. hero numbers on tiles) is TIER A —
the class that produces _two pages, two numbers_ inconsistency.

## Summary

- Files scanned: **210**
- KPI-rendering pages: **87**
- Pages with local truth-math (FREQ_DAYS / calcNextDue / ...): **0**
- **TIER A drift pages** (user-facing KPI surface): **0**
- TIER B drift pages (internal / shared JS): **0**
- Canonical reads: 302 · Drift: 0 · Gap: 0 · Allowed: 219
