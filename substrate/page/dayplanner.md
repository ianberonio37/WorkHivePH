---
name: page-dayplanner
type: page
source: file:dayplanner.html
source_sha: 97a98fe4f1f68e34
last_verified: 2026-07-13
supersedes: null
---
## page · `dayplanner.html` — Maintenance Day Planner: WorkHive

Size: 221KB · 65 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (4): `logbook.update`, `schedule_items.delete`, `schedule_items.update`, `schedule_items.upsert`
**RPC calls**: (none)
**Edge invokes**: (none)
**Truth views read**: `v_logbook_truth`, `v_pm_scope_items_truth`

**Functions**: _dpEndMins, _dpNormalizeCat, _dpPaintStatusButtons, _dpReopenWithAttempt, _dpRestoreDeleted, _dpRollbackLocal, _dpShowOverduePms, _dpSyncSidebarToggle, _ensureDpQueue, _fromWorkHive, _hrLabel, _localeNames, _mineFilter, _phtWallNow, _pmPlanned, addGroundedItem, addPmToDay, closeModal, deleteItemFromSupabase, deleteScheduleItem, dpCanonToDisplay, dpDisplayToCanon, fromDBRow, getItemStatus, getSchedColor, goToDilDay, goToday, itemsOnDate, layoutBlocks, loadLogbook, loadPlantWork, loadSchedule, miloLabel, navigate, onMiloClick, onSlotClick, onYiloDayClick, onYiloMonthClick, openAddModal, openEditModal, render, renderDILO, renderDayplannerSummary, renderMILO, renderPlantWorkSection, renderSidebar, renderWILO, renderYILO, saveScheduleItem, selectAndSchedule, selectLogbookItem, set, setCard, setItemStatus, showToast, switchView, syncItemToSupabase, syncSidebarState, timeToMins, toDBRow …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
