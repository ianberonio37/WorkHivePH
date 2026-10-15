---
name: page-pm-scheduler
type: page
source: file:pm-scheduler.html
source_sha: 7145e1c655f7e907
last_verified: 2026-07-13
supersedes: null
---
## page · `pm-scheduler.html` — PM Scheduler: WorkHive

Size: 205KB · 81 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (9): `hive_audit_log.insert`, `logbook.insert`, `pm_assets.delete`, `pm_assets.update`, `pm_completions.insert`, `pm_completions.update`, `pm_scope_items.insert`, `pm_scope_items.update`, `project_links.insert`
**RPC calls**: `create_pm_asset_with_tasks`, `get_pm_compliance_smrp`, `get_pm_ontime_delivery`
**Edge invokes**: `embed-entry`
**Truth views read**: `v_asset_truth`, `v_pm_scope_items_truth`

**Functions**: _MINE, _autoLinkPmToProject, _ensurePmQueue, _isMine, _mineFilter, _phtDayNumber, _pmSyncUrl, _typeToCategory, _xpNoteFor, addCustomItem, addTaskBackdropClick, canonFreq, catPill, closeAddTaskSheet, closeEditPMAsset, closeSheet, confirmDeleteAsset, critBadge, daysLabel, deleteAsset, embedPMEntry, embedPMFaultEntry, filterRegisteredAssets, formatDate, freqBadge, getAssetOverallStatus, getEnrichedItems, goAddAsset, goBack, goStep, init, loadData, loadMoreHistory, loadMorePM, loadRegisteredAssets, markDone, onCategoryChange, openAddTaskSheet, openDetail, openEditPMAsset, openSheet, pickRegisteredAsset, pickTaskChip, pmCompleteHandler, populateTemplateOptions, removeCustomItem, renderCatTabs, renderDashboard, renderDetail, renderPMSummary, renderPMUnknown, renderRegisteredAssets, renderReview, renderScopeList, renderStepIndicator, renderTaskChips, resetWizard, saveAsset, saveEditPMAsset, saveNewTask …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
