---
name: page-project-manager
type: page
source: file:project-manager.html
source_sha: 5530bf8e2f1e546d
last_verified: 2026-07-13
supersedes: null
---
## page · `project-manager.html` — Project Manager | WorkHive

Size: 167KB · 96 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (12): `project_change_orders.insert`, `project_change_orders.update`, `project_items.insert`, `project_items.update`, `project_links.delete`, `project_links.insert`, `project_progress_logs.insert`, `project_progress_logs.update`, `project_roles.delete`, `project_roles.insert`, `projects.insert`, `projects.update`
**RPC calls**: `generate_change_order_number`, `generate_project_code`
**Edge invokes**: `embed-entry`, `project-orchestrator`, `project-progress`
**Truth views read**: `v_inventory_items_truth`, `v_logbook_truth`, `v_marketplace_listings_truth`, `v_project_items_truth`, `v_project_progress_truth`, `v_project_truth`

**Functions**: _embedProjectAsync, _num, ackLog, aiDraftLessons, approveCO, bindFilters, buildDetailTabs, cancelCO, clientRollup, closeDetail, closeModal, combineNotes, cycleScopeStatus, daysBetween, deleteProject, fetchProgressRollup, fmtDate, fmtPHP, getFreeNotes, getPhase, isSupervisor, labelFor, linkSuggested, loadGroupState, loadHiveMembers, loadLinkOptions, loadProjects, loadRecents, markComplete, markStatus, openAIIntentModal, openAddRole, openDetail, openEditProject, openEditScope, openModal, openNewCO, openNewProject, openNewScope, openProgressLog, pcardHtml, populatePredecessors, progressColor, pushAIContext, pushRecent, refreshDetail, refreshSuggestedLinks, rejectCO, removeLink, removeRole, renderActivePane, renderBudget, renderChangeOrders, renderCpm, renderEmptyState, renderLinked, renderList, renderOverview, renderProgress, renderProjectsSummary …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
