---
name: page-marketplace-admin
type: page
source: file:marketplace-admin.html
source_sha: 23b881ad4e4592c2
last_verified: 2026-07-13
supersedes: null
---
## page · `marketplace-admin.html` — Marketplace Admin | WorkHive

Size: 51KB · 20 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (5): `hive_audit_log.insert`, `marketplace_disputes.update`, `marketplace_listings.update`, `marketplace_orders.update`, `marketplace_sellers.update`
**RPC calls**: (none)
**Edge invokes**: (none)
**Truth views read**: `v_marketplace_listings_truth`, `v_marketplace_sellers_truth`

**Functions**: _admSyncUrl, fmtPrice, handleDisputeAction, handleListingAction, handleSellerAction, initials, loadDisputes, loadListings, loadSellers, loadStats, renderDisputes, renderListings, renderSellers, showSkeletons, showToast, switchTab, timeAgo, updateStats, verifyPlatformAdmin, writeAuditLog

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
