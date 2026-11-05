---
name: page-logbook
type: page
source: file:logbook.html
source_sha: 5943ca4b79d1d630
last_verified: 2026-07-13
supersedes: null
---
## page · `logbook.html` — Digital Maintenance Logbook: WorkHive

Size: 551KB · 181 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (7): `asset_nodes.update`, `asset_nodes.upsert`, `hive_audit_log.insert`, `logbook.insert`, `logbook.update`, `pm_completions.insert`, `project_links.insert`
**RPC calls**: `advance_assigned_wo`, `inventory_deduct`, `logbook_synced_machines`, `notify_wo_assigned`, `set_logbook_wo`, `sync_asset_identity`
**Edge invokes**: `cmms-push-completion`, `embed-entry`, `equipment-label-ocr`, `visual-defect-capture`, `voice-logbook-entry`
**Truth views read**: `v_inventory_items_truth`, `v_inventory_transactions_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_pm_scope_items_truth`

**Functions**: _MINE, _afterDepartedChange, _assetToNode, _autoLinkLogbookToProject, _b64bytes, _canAdvanceAssigned, _canMoveWorkOrder, _canWriteEntry, _d, _departedEntry, _drainOfflineQueue, _e, _e2, _exportPageAll, _exportTeamAll, _hiveOf, _isAssignedToMe, _isMine, _lbHaystack, _lbIsRefusal, _lbListEl, _lbMarkArrived, _lbPersonalEmpty, _lbQueueError, _lbQueuedInsertLanded, _lbSaveUnexplained, _lbShowHiveAssets, _lbSyncFailurePanel, _logRestoreFilters, _logSyncUrl, _logXpNote, _mineFilter, _norm, _pollLogbookTeam, _queuedHive, _registerLogbookQueue, _setIf, _setPill, _setRadio, _setVal, _takesOverDeparted, _val, _vn, addEntry, advanceAssigned, applyRoleUI, applySmartVoiceFill, applyWoStateUI, assignDepartedEntry, cancelEditMode, catBadge, clearAssetForm, clearForm, closeAssetModal, closeAssetPicker, closeDepartedEntry, closeEditAsset, closePartsPicker, collectProductionOutput, collectReadings …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
