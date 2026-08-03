---
name: page-founder-console
type: page
source: file:founder-console.html
source_sha: e4b7da2c90a86df3
last_verified: 2026-07-13
supersedes: null
---
## page · `founder-console.html` — WorkHive Founder Console

Size: 166KB · 55 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (7): `marketplace_disputes.update`, `marketplace_listings.update`, `marketplace_sellers.update`, `platform_feedback.update`, `service_credit_topups.update`, `service_vouchers.insert`, `service_vouchers.update`
**RPC calls**: (none)
**Edge invokes**: (none)
**Truth views read**: `v_credit_posture`, `v_hive_readiness_truth`, `v_marketplace_listings_truth`, `v_marketplace_orders_truth`, `v_marketplace_sellers_truth`, `v_service_credit_ledger_truth`, `v_service_credit_topups_truth`

**Functions**: applyFeedbackView, closeFeedbackDrawer, dim, fetchActiveHivesCount, fetchAiCostByProvider, fetchAiCostToday, fetchAuditFeed, fetchCompanionEval, fetchDau14d, fetchHeatmap7d, fetchMarketplacePulse, fetchMaturityDistribution, fetchMau30d, fetchMementoHealth, fetchMktModeration, fetchPareto30d, fetchTechHealth, get, hideZeroStat, honestEmpty, loadCreditEconomy, loadSvcTopups, loadSvcVouchers, openFeedbackDrawer, refreshAll, renderAiCostDetail, renderAudit, renderCompanionEval, renderFeedbackInbox, renderGrowthPulse, renderHeatmap, renderHero, renderMarketplace, renderMaturity, renderMementoHealth, renderMktModeration, renderPareto, renderTLDR, renderTechHealth, saveDrawerChanges, setRagDot, setRagDots, setStat, setStatGap, setUpd, showToast, stat, statGapReason, subscribeFeedbackRealtime, svcMintVoucher, svcToggleVoucher, svcTopupDecide, timeAgo, wireMktModeration, wireRefreshControls

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
