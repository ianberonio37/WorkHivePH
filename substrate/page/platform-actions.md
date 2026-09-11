---
name: page-platform-actions
type: page
source: file:platform-actions.html
source_sha: 797c110d3e058568
last_verified: 2026-07-13
supersedes: null
---
## page · `platform-actions.html` — Platform Actions · WorkHive

Size: 106KB · 36 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (5): `hive_audit_log.insert`, `marketplace_listings.update`, `marketplace_sellers.update`, `platform_feedback.update`, `service_credit_topups.update`
**RPC calls**: `founder_active_hives`, `founder_anon_sessions`, `founder_dau_series`, `founder_mau`, `founder_page_heatmap`
**Edge invokes**: (none)
**Truth views read**: `v_credit_posture`, `v_gcash_receipts_needing_eyes`, `v_marketplace_listings_truth`, `v_marketplace_sellers_truth`, `v_service_credit_ledger_truth`, `v_service_credit_topups_truth`

**Functions**: _amtOrGap, _btnRestore, _modPrice, _queueErr, _restore, add, applyFeedbackView, closeFeedbackDrawer, emptyText, fbTimeAgo, fetchCreditPosition, fetchFeedback, fetchGcashLeftovers, fetchMktModeration, fetchSvcTopups, fetchUsage, num, ok, one, openFeedbackDrawer, refreshQueues, refusalMessage, renderCreditPosition, renderFeedback, renderGcashLeftovers, renderMktModeration, renderSvcTopups, renderUsage, saveFeedbackDrawer, setCount, showToast, subscribeFeedbackRealtime, wireFeedback, wireMktModeration, wireSvcTopups, writeAuditLog

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
