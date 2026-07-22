---
name: page-integrations
type: page
source: file:integrations.html
source_sha: 4b78fdde0eb92008
last_verified: 2026-07-13
supersedes: null
---
## page · `integrations.html` — CMMS Integration | WorkHive

Size: 124KB · 39 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (15): `api_keys.insert`, `api_keys.update`, `asset_nodes.upsert`, `cmms_audit_log.insert`, `cmms_audit_log.update`, `external_sync.delete`, `external_sync.upsert`, `integration_configs.delete`, `integration_configs.insert`, `integration_configs.update`, `inventory_items.upsert`, `logbook.insert`, `logbook.update`, `pm_assets.insert`, `pm_scope_items.insert`
**RPC calls**: (none)
**Edge invokes**: `cmms-sync`, `cmms-webhook-receiver`, `intelligence-api`
**Truth views read**: `v_external_sync_truth`, `v_logbook_truth`

**Functions**: _confidenceBadge, _updateConfidenceCell, autoSuggestMapping, buildMappingTable, buildPreview, computePatterns, computeQualityScore, dismissGuide, editConfig, generateApiKey, goStep, handleFile, loadApiKeys, loadConflicts, loadImportHistory, loadScriptOnce, loadSyncConfigs, normalizeRow, onMappingChange, pct, processRows, renderIntegrationsLoadError, renderIntegrationsSummary, resetWizard, resolveConflict, revokeKey, rollbackBatch, runSync, saveSyncConfig, scoreLabel, selectEntity, selectSource, setCard, showResults, showToast, startImport, switchTab, testSyncConfig, writeAuditLog

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
