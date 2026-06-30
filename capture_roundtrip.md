# §13 Capture Value-Correctness — payload-contract resolution

> For each of the 106 value-verifiable capture fields (PERSISTED + PERSISTED?), the exact DB column is resolved by parsing the surface's REAL insert/upsert payload (spread-following, ≤3-hop variable trace, mapper-rename modeling), and the read→persist path is classified. PASSTHROUGH/GUARD/BOOL = value-correct by construction; NUMERIC/RENAME/STRUCT = value-affecting (the FCU bug class, eligible for the live round-trip). Cross-checked vs the schema-confirmed set.

## Disposition

| Disposition | Count | Meaning |
|---|---|---|
| CONTRACT_VERIFIED | 79 | passthrough/guard/bool — no transform can corrupt the value |
| NEEDS_VALUE_CHECK | 16 | value-affecting transform — eligible live-round-trip set |
| UNRESOLVED | 11 | persist decoupled (positional args / computed branch / file upload) — honest |

**Columns newly named** (were indirected/transform-mapped): 45. **Cross-check**: PASS — all schema-confirmed columns agree.

## NEEDS_VALUE_CHECK (the value-affecting transforms)

| Surface | Field | → Column | Class | Source |
|---|---|---|---|---|
| asset-hub | fmea-detection | rcm_fmea_modes.detection | NUMERIC | `Number.isFinite(det) ? det : null ⟵ parseInt(document.getElementById('fmea-detec` |
| asset-hub | fmea-occurrence | rcm_fmea_modes.occurrence | NUMERIC | `Number.isFinite(occ) ? occ : null ⟵ parseInt(document.getElementById('fmea-occur` |
| asset-hub | fmea-severity | rcm_fmea_modes.severity | NUMERIC | `Number.isFinite(sev) ? sev : null ⟵ parseInt(document.getElementById('fmea-sever` |
| inventory | restock-qty | inventory_items.qty_on_hand | NUMERIC | `qty ⟵ parseFloat(document.getElementById('restock-qty').value) || 0` |
| logbook | a-type | asset_nodes.iso_class | RENAME | `document.getElementById('a-type').value` |
| logbook | f-downtime | logbook.downtime_hours | NUMERIC | `downtimeRaw !== '' ? parseFloat(downtimeRaw) : null ⟵ document.getElementById('f` |
| marketplace | post-price | marketplace_listings.price | NUMERIC | `price ⟵ priceRaw !== '' ? parseFloat(priceRaw) : null ⟵ document.getElementById(` |
| marketplace | review-rating | marketplace_reviews.rating | NUMERIC | `rating ⟵ parseInt(document.getElementById('review-rating')?.value || '0', 10)` |
| project-manager | co-cost | project_change_orders.cost_impact_php | NUMERIC | `$('co-cost').value ? Number($('co-cost').value) : null` |
| project-manager | co-days | project_change_orders.schedule_impact_days | NUMERIC | `$('co-days').value ? Number($('co-days').value) : null` |
| project-manager | f-budget | projects.budget_php | NUMERIC | `$('f-budget').value ? Number($('f-budget').value) : null` |
| project-manager | p-hours | project_progress_logs.hours_worked | NUMERIC | `$('p-hours').value ? Number($('p-hours').value) : null` |
| project-manager | p-pct | project_progress_logs.pct_complete | NUMERIC | `Number($('p-pct').value || 0)` |
| project-manager | s-est | project_items.estimated_hours | NUMERIC | `$('s-est').value ? Number($('s-est').value) : null` |
| project-manager | s-phase | project_items.notes | STRUCT | `combineNotes($('s-phase').value, $('s-notes').value)` |
| project-manager | wiz-budget | projects.budget_php | NUMERIC | `$('wiz-budget').value ? Number($('wiz-budget').value) : null` |

## UNRESOLVED (persist decoupled from field-read — honest)

| Surface | Field |
|---|---|
| asset-hub | rcm-interval |
| asset-hub | rcm-interval-custom |
| inventory | restock-note |
| inventory | use-job-ref |
| inventory | use-qty |
| marketplace | post-condition |
| marketplace | post-image-file |
| pm-scheduler | sheet-log-toggle |
| project-manager | l-picker |
| project-manager | l-text |
| project-manager | l-type |