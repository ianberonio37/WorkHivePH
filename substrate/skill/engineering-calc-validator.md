---
name: skill-engineering-calc-validator
type: skill
source: skill:engineering-calc-validator
source_sha: 93aed52446d5e896
last_verified: 2026-07-13
supersedes: null
---
## skill · engineering-calc-validator

A 4-layer automated validation suite for the WorkHive Engineering Design Calculator platform. It catches field name mismatches, broken contracts between Python handlers and renderers, and edge functio

**Sections:** Engineering Calc Validator Skill · What This Is · Quick (skip live edge function calls): · Full (includes edge function integration test): · When to Run · The 4 Layers · Layer 1 — Python API Unit Test (`validate_fields.py`) · Layer 2a — Renderer Contract Test (`validate_renderers.py`) · Layer 2b — BOM/SOW Contract Test (`validate_bom_sow.py`) · Layer 3 — Integration Test (`validate_integration.py`) · Standard Practice Summary · Common Failure Patterns and Fixes · Layer 1 FAIL: HTTP 500 · Layer 1 FAIL: not_implemented · Layer 1 FAIL: HTTP 422 · Layer 2a FAIL: r.fieldName NOT returned by API · Layer 2a FAIL: closest API key shown · Layer 3 FAIL: source='typescript' when expected 'python' · Layer 3 FAIL: results.field is null · Architecture Reference · Adding a New Calc Type — Checklist · Auto-learned (2026-04-27) · Auto-learned (2026-04-27) · Auto-learned (2026-04-27) · Auto-learned (2026-04-27) · Auto-learned (2026-04-27) · Auto-Fix Rules · rule: load-schedule-kva-alias · Layer 5 — VALUE Accuracy (the number, not just the field name) — 2026-06-17 · Layer 6 — LIVE value tier: the hermetic check passes on STALE source; replay the same oracles through the running API (2026-06-23, Arc Q)

(Deep source: `skill:engineering-calc-validator` — retrieve this TOC to know WHICH section to read.)
