---
name: page-inventory
type: page
source: file:inventory.html
source_sha: 3f46cf8a10e2fac2
last_verified: 2026-07-13
supersedes: null
---
## page · `inventory.html` — Spare-Parts Inventory: WorkHive

Size: 236KB · 75 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (6): `asset_nodes.upsert`, `hive_audit_log.insert`, `inventory_items.update`, `inventory_items.upsert`, `inventory_transactions.insert`, `project_links.insert`
**RPC calls**: `inventory_adjust`, `inventory_deduct`, `inventory_restock`
**Edge invokes**: (none)
**Truth views read**: `v_inventory_items_truth`, `v_inventory_transactions_truth`

**Functions**: _autoLinkInventoryToProject, _b64bytes, _buildAssetNodeMaps, _dropNew, _dropOld, _ensureInvQueue, _filterAssetLinker, _invFolded, _invListEl, _invMayApprove, _invRenderList, _invStat, _invSyncUrlQ, _itemHistoryHtml, _loadItemHistory, _loadOlderHistory, _mineFilter, _ownsItem, _redrawOpenDetail, _refreshAssetsForLinker, _stableUuid, addTransaction, approvalBadge, assetBadge, catBadge, closeDetailModal, closePartModal, closeRestockModal, closeUseModal, confirmDeleteItem, findOnMarketplace, fold, formatDate, getReservedFor, getReservedQty, hasQty, highlight, initData, invPhotoImg, invSetStatusFilter, invShowPending, inventoryDeductHandler, loadAssets, loadInventory, loadMoreInventory, loadTransactions, mergeById, openAddModal, openDetailModal, openRestockModal, openUseModal, qtyText, rankOf, renderAssetLinker, renderInventorySummary, renderParts, saveInventory, saveTransactions, sellSurplus, setCard …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
