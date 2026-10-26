---
name: page-inventory
type: page
source: file:inventory.html
source_sha: 7f6b0e497a68fe14
last_verified: 2026-07-13
supersedes: null
---
## page · `inventory.html` — Spare-Parts Inventory: WorkHive

Size: 222KB · 67 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (6): `asset_nodes.upsert`, `hive_audit_log.insert`, `inventory_items.update`, `inventory_items.upsert`, `inventory_transactions.insert`, `project_links.insert`
**RPC calls**: `inventory_adjust`, `inventory_deduct`, `inventory_restock`
**Edge invokes**: (none)
**Truth views read**: `v_inventory_items_truth`, `v_inventory_transactions_truth`

**Functions**: _autoLinkInventoryToProject, _b64bytes, _buildAssetNodeMaps, _dropNew, _dropOld, _ensureInvQueue, _invFolded, _invListEl, _invMayApprove, _invRenderList, _invStat, _invSyncUrlQ, _mineFilter, _ownsItem, addTransaction, approvalBadge, assetBadge, catBadge, closeDetailModal, closePartModal, closeRestockModal, closeUseModal, confirmDeleteItem, findOnMarketplace, formatDate, getReservedFor, getReservedQty, hasQty, highlight, initData, invPhotoImg, invSetStatusFilter, invShowPending, inventoryDeductHandler, loadAssets, loadInventory, loadMoreInventory, loadTransactions, mergeById, openAddModal, openDetailModal, openRestockModal, openUseModal, qtyText, rankOf, renderAssetLinker, renderInventorySummary, renderParts, saveInventory, saveTransactions, sellSurplus, setCard, setCta, setInventoryCompanionContext, showFormError, showToast, signal, statusBadge, stockStatus, submitPart …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
