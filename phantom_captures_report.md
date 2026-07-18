# Phantom Capture Audit (Layer -1.5 reverse-lineage)

Every HTML form field that no engine, brain, or dashboard reads.
Run by `tools/audit_phantom_captures.py`. Output is a deletion
candidates punch list. To keep a field, add `phantom-allow: <key> <reason>`
as an HTML comment on the capture page.

## Summary

- Capture fields discovered:  **235**
- Framework names skipped:    **2** (submit, search, csrf, ...)
- Alive (≥1 consumer):        **233** ✅
- Phantom (0 consumers):      **0** ❌
- Allowlisted (justified):    **0**

## Deletion candidates (0)

_None — every capture has at least one downstream consumer. Schema discipline is currently good; the gate locks this in against future drift._


## Low-usage candidates — `consumer_count == 1` (19)

Fields read in exactly one place. Likely fine (single-purpose),
but worth a scan for vestigial half-wired fields.

| Capture name | Captured on |
|---|---|
| `a-scan-input` | logbook.html |
| `cl-text` | resume.html |
| `custom-item-freq` | pm-scheduler.html |
| `fb-d-note` | founder-console.html |
| `fb-d-priority` | founder-console.html |
| `fb-d-public` | founder-console.html |
| `fb-filter-kind` | founder-console.html |
| `filter-route` | agentic-rag-observability.html |
| `filter-type` | project-manager.html |
| `filter-window` | agentic-rag-observability.html |
| `ho-handover-to` | hive.html |
| `pf-direction` | asset-hub.html |
| `pf-f-threshold` | asset-hub.html |
| `pf-p-threshold` | asset-hub.html |
| `pf-safety-critical` | asset-hub.html |
| `promote-dedupe` | resume.html |
| `rfq-contact` | marketplace.html |
| `save-search-email` | marketplace.html |
| `today-context` | assistant.html |

## What to do with a phantom

1. **Delete it** — if no business reason exists, remove the form field, the column,
   and any migration that adds it. This is the default and safe move.
2. **Justify it** — add an HTML comment on the capture page:
   `<!-- phantom-allow: <field-name> reason here -->`
   Use sparingly: each allowlist line is a maintenance promise.
3. **Wire a consumer** — if the field SHOULD power a dashboard tile or AI input,
   add the read site downstream. The auditor flips the field to alive on next run.