---
name: page-hive
type: page
source: file:hive.html
source_sha: 33c6e09c42e61a59
last_verified: 2026-07-13
supersedes: null
---
## page · `hive.html` — Hive Live Board: WorkHive

Size: 307KB · 90 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (7): `hive_audit_log.insert`, `hive_members.delete`, `hive_members.update`, `hive_members.upsert`, `hives.insert`, `hives.update`, `logbook.update`
**RPC calls**: `compute_adoption_risk`, `compute_hive_readiness`, `find_hive_by_code`, `get_adoption_risk_current`, `get_hive_board_dashboard`, `get_hive_readiness_current`, `join_hive_by_code`
**Edge invokes**: `ai-gateway`, `ai-orchestrator`, `benchmark-compute`, `supervisor-reset-password`
**Truth views read**: `v_ai_reports_truth`, `v_alert_truth`, `v_hives_truth`, `v_inventory_items_truth`, `v_knowledge_freshness_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_pm_scope_items_truth`, `v_skill_badges_truth`, `v_worker_truth`

**Functions**: _openIntentModal, _openWorkerProfileDrawer, _t, approveItem, arrangeSupervisorDash, askCoach, buildFeedCard, buildNotifications, buildPMCard, buildPartsCard, catStyle, check, checkStockAlert, checkTeamStockAlert, close, computeBenchmarkNow, copyHandover, genCode, generateHandover, getHiveList, initBoard, initHive, isOpen, kickMember, loadAdoptionCard, loadApprovalQueue, loadAuditLog, loadBenchmarks, loadFeed, loadKnowledgePipeline, loadMaturityStairway, loadMembers, loadMoreFeed, loadMyOpenWork, loadOnboardingCard, loadPMHealth, loadPatternAlerts, loadShiftRibbon, loadSupervisorSummary, loadTeamPulse, loadTodaysBrief, maybeShowIntentCapture, migrateLegacyHive, open, performLeave, prependFeed, printHandover, pushNotif, recoverHiveMembership, rejectItem, renderAdoptionCard, renderApprovalQueue, renderFeed, renderHiveFocus, renderHiveSwitcher, renderMaturityStairway, renderNotifs, renderPresence, renderPresenceFallback, resetMemberPassword …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
