---
name: page-platform-actions
type: page
source: file:platform-actions.html
source_sha: e7488f5600d2eee0
last_verified: 2026-07-13
supersedes: null
---
## page · `platform-actions.html` — Platform Actions · WorkHive

Size: 59KB · 23 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (5): `hive_audit_log.insert`, `marketplace_listings.update`, `marketplace_sellers.update`, `platform_feedback.update`, `service_credit_topups.update`
**RPC calls**: (none)
**Edge invokes**: (none)
**Truth views read**: `v_gcash_receipts_needing_eyes`, `v_marketplace_listings_truth`, `v_marketplace_sellers_truth`, `v_service_credit_topups_truth`

**Functions**: applyFeedbackView, closeFeedbackDrawer, emptyText, fbTimeAgo, fetchFeedback, fetchGcashLeftovers, fetchMktModeration, fetchSvcTopups, openFeedbackDrawer, refreshQueues, refusalMessage, renderFeedback, renderGcashLeftovers, renderMktModeration, renderSvcTopups, saveFeedbackDrawer, setCount, showToast, subscribeFeedbackRealtime, wireFeedback, wireMktModeration, wireSvcTopups, writeAuditLog

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
