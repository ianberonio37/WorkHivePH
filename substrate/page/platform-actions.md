---
name: page-platform-actions
type: page
source: file:platform-actions.html
source_sha: 7552f5fb68170f44
last_verified: 2026-07-13
supersedes: null
---
## page · `platform-actions.html` — Platform Actions · WorkHive

Size: 25KB · 10 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (4): `hive_audit_log.insert`, `marketplace_listings.update`, `marketplace_sellers.update`, `service_credit_topups.update`
**RPC calls**: (none)
**Edge invokes**: (none)
**Truth views read**: `v_marketplace_listings_truth`, `v_marketplace_sellers_truth`, `v_service_credit_topups_truth`

**Functions**: fetchMktModeration, fetchSvcTopups, refreshQueues, renderMktModeration, renderSvcTopups, setCount, showToast, wireMktModeration, wireSvcTopups, writeAuditLog

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
