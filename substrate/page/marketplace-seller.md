---
name: page-marketplace-seller
type: page
source: file:marketplace-seller.html
source_sha: 8d85519673583b75
last_verified: 2026-07-13
supersedes: null
---
## page · `marketplace-seller.html` — Seller Dashboard: WorkHive Marketplace

Size: 74KB · 28 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (5): `hive_audit_log.insert`, `marketplace_inquiries.update`, `marketplace_listings.delete`, `marketplace_listings.update`, `marketplace_sellers.upsert`
**RPC calls**: (none)
**Edge invokes**: (none)
**Truth views read**: `v_marketplace_inquiries_truth`, `v_marketplace_listings_truth`, `v_marketplace_sellers_truth`

**Functions**: _selSyncUrl, compressImageFile, fmtPrice, handleCloseInquiry, handleDelete, handleEditSubmit, handleReply, handleSaveCerts, handleSaveMessenger, initials, loadAnalytics, loadInquiries, loadListings, loadProfile, openEditSheet, preloadEditImageFromExisting, renderInquiries, renderListings, resetEditImagePicker, showSkeletons, showToast, switchTab, timeAgo, updateBadges, updateProfileStats, uploadImageBlob, wireEditImagePicker, writeAuditLog

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
