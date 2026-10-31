---
name: page-platform-actions
type: page
source: file:platform-actions.html
source_sha: d0047d57c96dece3
last_verified: 2026-07-13
supersedes: null
---
## page · `platform-actions.html` — Platform Actions · WorkHive

Size: 165KB · 53 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (4): `marketplace_listings.update`, `marketplace_sellers.update`, `platform_feedback.update`, `service_credit_topups.update`
**RPC calls**: `adjudicate_service_dispute`, `admin_disputed_jobs`, `founder_active_hives`, `founder_anon_sessions`, `founder_dau_series`, `founder_feature_use`, `founder_mau`, `founder_page_heatmap`, `get_credit_ledger_totals`
**Edge invokes**: (none)
**Truth views read**: `v_credit_posture`, `v_gcash_receipts_needing_eyes`, `v_marketplace_listings_truth`, `v_marketplace_sellers_truth`, `v_service_credit_topups_truth`

**Functions**: _amtOrGap, _btnRestore, _modPrice, _offlineGate, _orIlike, _queueErr, _restore, _usesBlock, add, applyFeedbackView, closeFeedbackDrawer, emptyText, fbTimeAgo, fetchCreditPosition, fetchDecisions, fetchDisputes, fetchFeedback, fetchGcashLeftovers, fetchMktModeration, fetchPublished, fetchSvcTopups, fetchUsage, fetchVerifiedSellers, line, num, ok, one, openFeedbackDrawer, refreshQueues, refusalMessage, renderCreditPosition, renderDecisions, renderDisputes, renderFeedback, renderGcashLeftovers, renderMktModeration, renderPublished, renderSvcTopups, renderUsage, renderVerifiedSellers, saveFeedbackDrawer, searchPublished, searchVerifiedSellers, setCount, showToast, subscribeFeedbackRealtime, when, wireDisputes, wireFeedback, wireMktModeration, wirePublishedSearch, wireSvcTopups, wireVerifiedSearch

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
