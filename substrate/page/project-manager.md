---
name: page-project-manager
type: page
source: file:project-manager.html
source_sha: 6b35f9ec009b8807
last_verified: 2026-07-13
supersedes: null
---
## page · `project-manager.html` — Project Manager | WorkHive

Size: 247KB · 107 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (10): `project_change_orders.insert`, `project_change_orders.update`, `project_items.insert`, `project_items.update`, `project_links.insert`, `project_progress_logs.insert`, `project_progress_logs.update`, `project_roles.insert`, `projects.insert`, `projects.update`
**RPC calls**: `generate_change_order_number`, `generate_project_code`, `get_project_budget`, `set_project_budget`
**Edge invokes**: `embed-entry`, `project-orchestrator`, `project-progress`
**Truth views read**: `v_inventory_items_truth`, `v_logbook_truth`, `v_marketplace_listings_truth`, `v_project_items_truth`, `v_project_progress_truth`, `v_project_truth`

**Functions**: _aiTxt, _clearSt, _embedProjectAsync, _num, _pmQueue, _pmRecentlyRemoved, _pmTrustLessons, _qid, _todayIso, ackLog, aiDraftLessons, approveCO, bindFilters, buildDetailTabs, cancelCO, clientRollup, closeDetail, closeModal, combineNotes, cycleScopeStatus, daysBetween, deleteProject, fetchProgressRollup, fmtDate, fmtPHP, getFreeNotes, getPhase, importBomItems, isSupervisor, labelFor, linkSuggested, loadGroupState, loadHiveMembers, loadLinkOptions, loadProjects, loadRecents, markComplete, markStatus, openAIIntentModal, openAddRole, openBomImport, openDetail, openEditProject, openEditScope, openModal, openNewCO, openNewProject, openNewScope, openProgressLog, pcardHtml, populatePredecessors, progressColor, pushAIContext, pushRecent, refreshDetail, refreshSuggestedLinks, rejectCO, releaseCO, removeLink, removeRole …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
