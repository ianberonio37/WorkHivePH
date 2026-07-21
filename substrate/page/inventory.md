---
name: page-inventory
type: page
source: file:inventory.html
source_sha: 40f7956049695e6a
last_verified: 2026-07-13
supersedes: null
---
## page · `inventory.html` — Spare-Parts Inventory: WorkHive

Size: 126KB · 49 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (7): `asset_nodes.upsert`, `hive_audit_log.insert`, `inventory_items.delete`, `inventory_items.update`, `inventory_items.upsert`, `inventory_transactions.insert`, `project_links.insert`
**RPC calls**: `inventory_deduct`, `inventory_restock`
**Edge invokes**: (none)
**Truth views read**: `v_inventory_items_truth`, `v_inventory_transactions_truth`

**Functions**: _autoLinkInventoryToProject, _b64bytes, _buildAssetNodeMaps, _invSyncUrlQ, addTransaction, approvalBadge, assetBadge, catBadge, closeDetailModal, closePartModal, closeRestockModal, closeUseModal, confirmDeleteItem, findOnMarketplace, formatDate, getReservedQty, highlight, initData, inventoryDeductHandler, loadAssets, loadInventory, loadMoreInventory, loadTransactions, mergeById, openAddModal, openDetailModal, openRestockModal, openUseModal, renderAssetLinker, renderInventorySummary, renderParts, saveInventory, saveTransactions, sellSurplus, setCard, setCta, setInventoryCompanionContext, showFormError, showToast, statusBadge, stockStatus, submitPart, submitRestock, submitUse, subscribeInventoryRealtime, tryRegister, txnIcon, validateHiveMembership, writeAuditLog

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
