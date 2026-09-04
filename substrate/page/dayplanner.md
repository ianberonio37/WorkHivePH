---
name: page-dayplanner
type: page
source: file:dayplanner.html
source_sha: 89cd48782cac0fe0
last_verified: 2026-07-13
supersedes: null
---
## page · `dayplanner.html` — Maintenance Day Planner: WorkHive

Size: 138KB · 50 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (3): `logbook.update`, `schedule_items.delete`, `schedule_items.upsert`
**RPC calls**: (none)
**Edge invokes**: (none)
**Truth views read**: `v_logbook_truth`, `v_pm_scope_items_truth`

**Functions**: _ensureDpQueue, addGroundedItem, addPmToDay, closeModal, deleteItemFromSupabase, deleteScheduleItem, dpCanonToDisplay, dpDisplayToCanon, fromDBRow, getItemStatus, getSchedColor, goToDilDay, goToday, itemsOnDate, layoutBlocks, loadLogbook, loadPlantWork, loadSchedule, miloLabel, navigate, onMiloClick, onSlotClick, onYiloDayClick, onYiloMonthClick, openAddModal, openEditModal, render, renderDILO, renderDayplannerSummary, renderMILO, renderPlantWorkSection, renderSidebar, renderWILO, renderYILO, saveScheduleItem, selectAndSchedule, selectLogbookItem, setCard, setItemStatus, showToast, switchView, syncItemToSupabase, syncSidebarState, timeToMins, toDBRow, toYMD, todayYMD, toggleSidebar, uid, ymdLabelDate

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
