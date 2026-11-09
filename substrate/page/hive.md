---
name: page-hive
type: page
source: file:hive.html
source_sha: 57849d2d4ef1b860
last_verified: 2026-07-13
supersedes: null
---
## page · `hive.html` — Hive Live Board: WorkHive

Size: 555KB · 133 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (7): `hive_audit_log.insert`, `hive_members.delete`, `hive_members.update`, `hive_members.upsert`, `hives.insert`, `hives.update`, `logbook.update`
**RPC calls**: `bring_personal_history_into_hive`, `compute_adoption_risk`, `deactivate_my_account`, `find_hive_by_code`, `get_adoption_risk_current`, `get_hive_board_dashboard`, `get_hive_readiness_current`, `join_hive_by_code`, `my_personal_history_count`, `my_recent_removal`, `notify_submission_decided`, `refresh_hive_readiness`, `set_federated_benchmark_opt_in`, `set_worker_display_name`
**Edge invokes**: `ai-gateway`, `ai-orchestrator`, `export-hive-data`, `supervisor-reset-password`
**Truth views read**: `v_ai_reports_truth`, `v_alert_truth`, `v_amc_truth`, `v_hive_value_summary`, `v_hives_truth`, `v_inventory_items_truth`, `v_knowledge_freshness_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_pm_scope_items_truth`, `v_skill_badges_truth`, `v_worker_assignment_truth`, `v_worker_truth`

**Functions**: _MINE, _hint, _hvLeaveBusy, _isReaderName, _loadBenchmarkSharing, _loadSharingNote, _mineFilter, _nBrief, _nFmea, _nStrat, _offerPersonalHistory, _open, _openIntentModal, _openWorkerProfileDrawer, _performLeaveOnce, _releaseSave, _renameHiveInner, _s, _sub, _swRole, _t, _teardownHiveBoard, _tellRecentRemoval, _whDropInviteParam, _whHonourInvite, _whInviteCode, _whIsSelf, _whRemovedYou, _whSeatInvitedHive, applyHiveRole, approveItem, arrangeSupervisorDash, askCoach, buildFeedCard, buildNotifications, buildPMCard, buildPartsCard, catStyle, check, checkStockAlert, checkTeamStockAlert, clamp, close, code, copyHandover, genCode, generateHandover, getHiveList, head, initBoard, initHive, isOpen, kickMember, link, loadAdoptionCard, loadApprovalQueue, loadAuditLog, loadBenchmarks, loadFeed, loadKnowledgePipeline …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
