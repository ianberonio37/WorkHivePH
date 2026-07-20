---
name: page-marketplace
type: page
source: file:marketplace.html
source_sha: 1ce2172e17685b33
last_verified: 2026-07-13
supersedes: null
---
## page · `marketplace.html` — Marketplace: WorkHive

Size: 164KB · 63 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (8): `hive_audit_log.insert`, `marketplace_inquiries.insert`, `marketplace_listings.insert`, `marketplace_saved_searches.delete`, `marketplace_saved_searches.insert`, `marketplace_saved_searches.update`, `marketplace_watchlist.delete`, `marketplace_watchlist.insert`
**RPC calls**: `get_community_reputation`, `get_marketplace_parts_for_my_assets`, `get_marketplace_price_comps`, `get_marketplace_trust_badges`, `get_saved_search_matches`, `increment_listing_view`
**Edge invokes**: `marketplace-listing-assist`
**Truth views read**: `v_inventory_items_truth`, `v_marketplace_listings_truth`, `v_marketplace_sellers_truth`

**Functions**: _blobToDataUrl, _mktSyncUrl, applySavedSearch, buildRfqTemplate, buildSearchSummary, cardHtml, clearCompare, closeSheet, compressImageFile, computeListingQuality, condClass, condLabel, deleteSavedSearch, fmtPrice, handleAiAssist, handleInquirySubmit, handlePostSubmit, handleSaveCurrentSearch, handleSubmitRfq, hasActiveFilters, initials, loadCounts, loadListings, loadWatchlist, mapInventoryCategory, onPriceInput, openDetailSheet, openInquirySheet, openPostSheet, openRfqSheet, openSavedSearchesSheet, openSheet, openWatchlistSheet, populateCategorySelect, prefillPostFromInventory, renderFilterChips, renderListings, renderMarketplaceSummary, renderPartsForMyAssets, renderStars, resetPostImagePicker, setCard, setMarketplaceCompanionContext, showSkeletons, showToast, startRealtime, switchSection, syncCompareBar, syncHeartIcons, tierOf, timeAgo, toggleCompareItem, toggleCompareMode, toggleWatchlist, updateCountBadges, updateLoadMoreBtn, updatePriceHint, updateQualityWidget, updateSavedSearchBadge, uploadImageBlob …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
