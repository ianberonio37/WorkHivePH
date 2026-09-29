---
name: page-dayplanner
type: page
source: file:dayplanner.html
source_sha: c5ef1f4e74764f08
last_verified: 2026-07-13
supersedes: null
---
## page · `dayplanner.html` — Maintenance Day Planner: WorkHive

Size: 207KB · 60 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (4): `logbook.update`, `schedule_items.delete`, `schedule_items.update`, `schedule_items.upsert`
**RPC calls**: (none)
**Edge invokes**: (none)
**Truth views read**: `v_logbook_truth`, `v_pm_scope_items_truth`

**Functions**: _dpEndMins, _dpNormalizeCat, _dpPaintStatusButtons, _dpReopenWithAttempt, _dpRestoreDeleted, _dpRollbackLocal, _dpSyncSidebarToggle, _ensureDpQueue, _hrLabel, _localeNames, addGroundedItem, addPmToDay, closeModal, deleteItemFromSupabase, deleteScheduleItem, dpCanonToDisplay, dpDisplayToCanon, fromDBRow, getItemStatus, getSchedColor, goToDilDay, goToday, itemsOnDate, layoutBlocks, loadLogbook, loadPlantWork, loadSchedule, miloLabel, navigate, onMiloClick, onSlotClick, onYiloDayClick, onYiloMonthClick, openAddModal, openEditModal, render, renderDILO, renderDayplannerSummary, renderMILO, renderPlantWorkSection, renderSidebar, renderWILO, renderYILO, saveScheduleItem, selectAndSchedule, selectLogbookItem, set, setCard, setItemStatus, showToast, switchView, syncItemToSupabase, syncSidebarState, timeToMins, toDBRow, toYMD, todayYMD, toggleSidebar, uid, ymdLabelDate

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
