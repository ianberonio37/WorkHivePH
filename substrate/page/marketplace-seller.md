---
name: page-marketplace-seller
type: page
source: file:marketplace-seller.html
source_sha: fc92715cb4fc102e
last_verified: 2026-07-13
supersedes: null
---
## page · `marketplace-seller.html` — Seller Dashboard: WorkHive Marketplace

Size: 131KB · 53 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (11): `hive_audit_log.insert`, `marketplace_inquiries.update`, `marketplace_listings.delete`, `marketplace_listings.update`, `marketplace_reviews.insert`, `marketplace_sellers.upsert`, `push_subscriptions.upsert`, `service_credit_topups.insert`, `service_providers.insert`, `service_providers.update`, `service_requests.update`
**RPC calls**: `accept_service_request`, `claim_starter_grant`, `my_service_provider_ids`, `provider_credit_balance`, `seller_credit_balance`, `submit_service_quote`
**Edge invokes**: (none)
**Truth views read**: `v_marketplace_inquiries_truth`, `v_marketplace_listings_truth`, `v_marketplace_sellers_truth`, `v_service_catalog_truth`, `v_service_credit_ledger_truth`, `v_service_open_broadcasts`, `v_service_provider_truth`, `v_service_request_truth`

**Functions**: _selSyncUrl, _svcB64ToU8, _svcGeoIndicator, _svcPeso, claimStarter, compressImageFile, fmtPrice, handleCloseInquiry, handleDelete, handleEditSubmit, handleReply, handleSaveCerts, handleSaveMessenger, initials, keepClosedSheetInert, loadAnalytics, loadCreditWallet, loadInquiries, loadListings, loadProfile, loadServices, openEditSheet, preloadEditImageFromExisting, renderInquiries, renderListings, renderSvcConsole, renderSvcOnboard, resetEditImagePicker, showSkeletons, showToast, svcAccept, svcAdvance, svcCancelJob, svcEnablePush, svcFileTopup, svcGeoSync, svcJobPollSync, svcProvPickStar, svcPushSupported, svcQuote, svcRateClient, svcRegister, svcRegisterHive, svcRequireOnline, svcToggleAvail, svcWalletHtml, switchTab, timeAgo, updateBadges, updateProfileStats, uploadImageBlob, wireEditImagePicker, writeAuditLog

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
