---
name: page-logbook
type: page
source: file:logbook.html
source_sha: 0b6191a43fd1e54f
last_verified: 2026-07-13
supersedes: null
---
## page · `logbook.html` — Digital Maintenance Logbook: WorkHive

Size: 299KB · 127 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (10): `asset_nodes.delete`, `asset_nodes.update`, `asset_nodes.upsert`, `hive_audit_log.insert`, `logbook.delete`, `logbook.insert`, `logbook.update`, `pm_assets.update`, `pm_completions.insert`, `project_links.insert`
**RPC calls**: `inventory_deduct`
**Edge invokes**: `cmms-push-completion`, `embed-entry`, `equipment-label-ocr`, `visual-defect-capture`, `voice-logbook-entry`
**Truth views read**: `v_external_sync_truth`, `v_inventory_items_truth`, `v_inventory_transactions_truth`, `v_pm_compliance_truth`, `v_pm_scope_items_truth`

**Functions**: _assetToNode, _autoLinkLogbookToProject, _b64bytes, _logRestoreFilters, _logSyncUrl, _registerLogbookQueue, _setIf, _setRadio, _setVal, _val, addEntry, applyRoleUI, applySmartVoiceFill, applyWoStateUI, cancelEditMode, catBadge, clearAssetForm, clearForm, closeAssetModal, closeAssetPicker, closeEditAsset, closePartsPicker, collectProductionOutput, collectReadings, confirmDelete, criticalityBadge, daysLabel, deleteAsset, deleteEntry, embedFaultEntry, fitsAsset, flash, formatDate, getPendingEntries, getTasklist, highlight, initAssets, kindTakesReadings, loadAssetDetail, loadAssets, loadEntries, loadInventoryForPicker, loadMachineHistory, loadMoreLogbook, loadPMTasksForAsset, loadReadingTemplates, loadSyncedMachines, loadTeamMembers, logbookCreateHandler, openAssetDetail, openAssetModal, openAssetPicker, openDeep, openEditAsset, openEditModal, openModal, openOfflineDB, openPartsPicker, openPartsPickerForEdit, queueEntryOffline …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
