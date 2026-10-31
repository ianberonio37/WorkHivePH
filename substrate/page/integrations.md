---
name: page-integrations
type: page
source: file:integrations.html
source_sha: 28b285f17689d268
last_verified: 2026-07-13
supersedes: null
---
## page · `integrations.html` — CMMS Integration | WorkHive

Size: 252KB · 73 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (22): `api_keys.insert`, `api_keys.update`, `asset_nodes.delete`, `asset_nodes.insert`, `asset_nodes.upsert`, `cmms_audit_log.insert`, `cmms_audit_log.update`, `external_sync.delete`, `external_sync.update`, `external_sync.upsert`, `integration_configs.delete`, `integration_configs.insert`, `integration_configs.update`, `inventory_items.delete`, `inventory_items.insert`, `inventory_items.upsert`, `logbook.insert`, `logbook.update`, `pm_assets.delete`, `pm_assets.insert`, `pm_scope_items.delete`, `pm_scope_items.insert`
**RPC calls**: (none)
**Edge invokes**: `cmms-sync`, `cmms-webhook-receiver`, `intelligence-api`
**Truth views read**: `v_external_sync_truth`, `v_hives_truth`, `v_logbook_truth`

**Functions**: _canon, _canonOf, _confidenceBadge, _conflictCardHtml, _conflictFind, _conflictMore, _itFailWhy, _lastPerId, _mapGet, _noun, _renderConflictList, _renderIntegrationsSourceChipOnLoad, _startImportInner, _updateConfidenceCell, autoSuggestMapping, buildMappingTable, buildPreview, computePatterns, computeQualityScore, dismissGuide, editConfig, esc, fold, generateApiKey, goStep, handleFile, landWhatFits, loadApiKeys, loadConflicts, loadImportHistory, loadScriptOnce, loadSyncConfigs, normalizeRow, onMappingChange, pct, processRows, renderIntegrationsLoadError, renderIntegrationsSummary, resetWizard, resolveConflict, revokeKey, rollbackBatch, runSync, saveSyncConfig, scoreLabel, selectEntity, selectSource, setCard, setIfEmpty, showResults, showToast, startImport, step, switchTab, takeBack, testSyncConfig, vehApplyRangerPreset, vehBack, vehCloseWizard, vehCreate …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
