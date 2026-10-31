---
name: page-project-manager
type: page
source: file:project-manager.html
source_sha: 10260e8b83090497
last_verified: 2026-07-13
supersedes: null
---
## page · `project-manager.html` — Project Manager | WorkHive

Size: 261KB · 116 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (10): `project_change_orders.insert`, `project_change_orders.update`, `project_items.insert`, `project_items.update`, `project_links.insert`, `project_progress_logs.insert`, `project_progress_logs.update`, `project_roles.insert`, `projects.insert`, `projects.update`
**RPC calls**: `generate_change_order_number`, `generate_project_code`, `get_project_budget`, `project_rollups`, `set_project_budget`
**Edge invokes**: `embed-entry`, `project-orchestrator`, `project-progress`
**Truth views read**: `v_inventory_items_truth`, `v_logbook_truth`, `v_marketplace_listings_truth`, `v_project_items_truth`, `v_project_progress_truth`, `v_project_truth`

**Functions**: _aiTxt, _by, _clearSt, _d, _embedProjectAsync, _hold, _linkSearchSoon, _num, _opts, _pmQueue, _pmRecentlyRemoved, _pmTrustLessons, _qid, _refill, _todayIso, ackLog, aiDraftLessons, allIn, anyOf, approveCO, bindFilters, buildDetailTabs, cancelCO, clientRollup, closeDetail, closeModal, combineNotes, cycleScopeStatus, daysBetween, deleteProject, failed, fetchProgressRollup, fmtDate, fmtPHP, getFreeNotes, getPhase, importBomItems, isSupervisor, labelFor, linkSuggested, loadGroupState, loadHiveMembers, loadLinkOptions, loadProjects, loadRecents, markComplete, markStatus, openAIIntentModal, openAddRole, openBomImport, openDetail, openEditProject, openEditScope, openModal, openNewCO, openNewProject, openNewScope, openProgressLog, pcardHtml, populatePredecessors …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
