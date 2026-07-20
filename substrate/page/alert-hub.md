---
name: page-alert-hub
type: page
source: file:alert-hub.html
source_sha: f9f6c836f1911466
last_verified: 2026-07-13
supersedes: null
---
## page · `alert-hub.html` — Alert Hub | WorkHive

Size: 91KB · 29 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (5): `alert_dismissals.delete`, `alert_dismissals.upsert`, `amc_briefings.update`, `anomaly_signals.update`, `hive_audit_log.insert`
**RPC calls**: `compute_anomaly_signals`
**Edge invokes**: `analytics-orchestrator`
**Truth views read**: `v_alert_truth`, `v_anomaly_truth`, `v_inventory_items_truth`, `v_pm_scope_items_truth`, `v_risk_truth`

**Functions**: _activeKind, _scheduleAnomalyReload, acknowledgeAlert, actOnAmcBrief, dismissAlert, fetchAmcBriefings, fmtRelative, fmtTime, hideCta, loadAll, loadAnomalyEngine, loadUnifiedAmcBrief, renderAlertSummary, renderAmcCard, renderAnomalyEngine, renderFeed, renderFilters, setCard, setCta, setStat, showAmcMsg, showToast, startAmcRealtime, startAnomalyRealtime, startRefresh, stopRefresh, todayPhtIso, wireAmcCardOnce, writeAuditLog

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
