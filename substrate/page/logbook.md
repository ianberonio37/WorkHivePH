---
name: page-logbook
type: page
source: file:logbook.html
source_sha: 1aa8d7a4edf62ad0
last_verified: 2026-07-13
supersedes: null
---
## page · `logbook.html` — Digital Maintenance Logbook: WorkHive

Size: 477KB · 151 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (9): `asset_nodes.delete`, `asset_nodes.update`, `asset_nodes.upsert`, `hive_audit_log.insert`, `logbook.delete`, `logbook.insert`, `logbook.update`, `pm_completions.insert`, `project_links.insert`
**RPC calls**: `inventory_deduct`, `notify_wo_assigned`, `sync_asset_identity`
**Edge invokes**: `cmms-push-completion`, `embed-entry`, `equipment-label-ocr`, `visual-defect-capture`, `voice-logbook-entry`
**Truth views read**: `v_external_sync_truth`, `v_inventory_items_truth`, `v_inventory_transactions_truth`, `v_pm_compliance_truth`, `v_pm_scope_items_truth`

**Functions**: _MINE, _assetToNode, _autoLinkLogbookToProject, _b64bytes, _canWriteEntry, _d, _drainOfflineQueue, _e, _e2, _exportPageAll, _exportTeamAll, _hiveOf, _lbIsRefusal, _lbQueueError, _lbQueuedInsertLanded, _lbSyncFailurePanel, _logRestoreFilters, _logSyncUrl, _mineFilter, _queuedHive, _registerLogbookQueue, _setIf, _setPill, _setRadio, _setVal, _val, _vn, addEntry, applyRoleUI, applySmartVoiceFill, applyWoStateUI, cancelEditMode, catBadge, clearAssetForm, clearForm, closeAssetModal, closeAssetPicker, closeEditAsset, closePartsPicker, collectProductionOutput, collectReadings, confirmDelete, consequenceBadge, criticalityBadge, daysLabel, deleteAsset, deleteEntry, embedFaultEntry, explainZeroRowWrite, fitsAsset, formatDate, getPendingEntries, getTasklist, highlight, initAssets, kindTakesReadings, lbAiKeptFields, lbAiSameValue, lbNoteAiFill, lbReadAiAssistedFields …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
