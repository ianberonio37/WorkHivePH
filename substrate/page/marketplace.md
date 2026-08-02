---
name: page-marketplace
type: page
source: file:marketplace.html
source_sha: 5c0ab140a483be8c
last_verified: 2026-07-13
supersedes: null
---
## page · `marketplace.html` — Marketplace: WorkHive

Size: 232KB · 88 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (11): `hive_audit_log.insert`, `marketplace_inquiries.insert`, `marketplace_listings.insert`, `marketplace_reviews.insert`, `marketplace_saved_searches.delete`, `marketplace_saved_searches.insert`, `marketplace_saved_searches.update`, `marketplace_watchlist.delete`, `marketplace_watchlist.insert`, `service_requests.insert`, `service_requests.update`
**RPC calls**: `get_community_reputation`, `get_marketplace_parts_for_my_assets`, `get_marketplace_price_comps`, `get_marketplace_trust_badges`, `get_saved_search_matches`, `increment_listing_view`, `redeem_service_voucher`, `select_quote`
**Edge invokes**: `ai-gateway`, `marketplace-listing-assist`
**Truth views read**: `v_inventory_items_truth`, `v_marketplace_inquiries_truth`, `v_marketplace_listings_truth`, `v_marketplace_sellers_truth`, `v_service_area_presence`, `v_service_catalog_truth`, `v_service_job_tracking`, `v_service_provider_truth`, `v_service_request_truth`

**Functions**: _blobToDataUrl, _mktSyncUrl, _prefill, _svcMapLoad, applySavedSearch, buildRfqTemplate, buildSearchSummary, cardHtml, clearCompare, closeSheet, compressImageFile, computeListingQuality, condClass, condLabel, deleteSavedSearch, fmtPrice, handleAiAssist, handleInquirySubmit, handlePostSubmit, handleSaveCurrentSearch, handleSubmitRfq, hasActiveFilters, initials, injectListingJsonLd, loadClientServices, loadCounts, loadListings, loadWatchlist, mapInventoryCategory, onPriceInput, openDetailSheet, openInquirySheet, openPostSheet, openRfqSheet, openSavedSearchesSheet, openSheet, openWatchlistSheet, populateCategorySelect, prefillPostFromInventory, renderClientServices, renderFilterChips, renderListings, renderMarketplaceSummary, renderPartsForMyAssets, renderStars, requireAccount, requirePostAccount, resetPostImagePicker, setCard, setMarketplaceCompanionContext, show, showSkeletons, showToast, startRealtime, svcApplyVoucher, svcAskQuotes, svcClientCancel, svcHailNow, svcLoadPresence, svcPickQuote …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
