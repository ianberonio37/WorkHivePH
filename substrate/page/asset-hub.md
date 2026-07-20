---
name: page-asset-hub
type: page
source: file:asset-hub.html
source_sha: 70c13c8aa04e19e3
last_verified: 2026-07-13
supersedes: null
---
## page · `asset-hub.html` — Asset Hub | WorkHive

Size: 203KB · 74 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (12): `asset_nodes.update`, `hive_audit_log.insert`, `parts_staged_reservations.insert`, `parts_staging_recommendations.update`, `pm_assets.insert`, `pm_scope_items.insert`, `rcm_fmea_modes.delete`, `rcm_fmea_modes.insert`, `rcm_fmea_modes.update`, `rcm_strategies.delete`, `rcm_strategies.insert`, `rcm_strategies.update`
**RPC calls**: (none)
**Edge invokes**: `ai-gateway`, `asset-brain-query`, `fmea-populator`, `pf-calculator`, `weibull-fitter`
**Truth views read**: `v_asset_truth`, `v_external_sync_truth`, `v_fmea_truth`, `v_logbook_truth`, `v_marketplace_listings_truth`, `v_pf_truth`, `v_rcm_truth`, `v_risk_truth`, `v_sensor_recent`, `v_sensor_truth`, `v_weibull_truth`

**Functions**: _ensurePfTemplates, _hexToRgb, _intervalToFrequencyLabel, _loadLatestPfFor, _onStagingAccept, _onStagingDismiss, _parsePartsField, _populatePfParameterSelect, _renderPfResult, _renderReliabilityReportHtml, _renderStagingCard, _renderWeibullFit, _rpnSeverityClass, _showRiskCard, _showRiskEmpty, _syncAssetView, approveAssetNode, approveFmeaMode, approveStrategy, askAssetBrain, assetLookupHandler, close, closeDetail, computePfInterval, computeWeibullFit, critClass, deleteFmeaMode, deleteStrategy, esc, fmtDate, fmtRelative, generateReliabilityReport, hideCta, init, loadAssetNodes, loadDetailExternalIds, loadDetailFmea, loadDetailHeader, loadDetailMarketplace, loadDetailRisk, loadDetailStaging, loadDetailStats, loadDetailTelemetry, loadDetailTimeline, loadLatestWeibull, loadPendingAssets, loadPfPanel, onEsc, openDetail, openFmeaModal, openStrategyModal, pushStrategyToPm, rejectAssetNode, renderAssetSummary, renderFmeaList, renderList, renderPendingAssets, resolvePmAssetId, restoreAssetNode, riskChip …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
