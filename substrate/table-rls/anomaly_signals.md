---
name: table-rls-anomaly_signals
type: table-rls
source: db:pg_policies+pg_trigger:anomaly_signals
source_sha: f49ad855a43e12ff
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `anomaly_signals` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, snapshot_date*, machine*, asset_node_id, composite_score*, logbook_cluster_score*, sensor_zscore_score*, pm_drift_score*, parts_spend_score*, failure_signature_score*, source_count*, severity*, top_reasons*, evidence*, status*, acknowledged_by, acknowledged_at, resolved_by, resolved_at, computed_at*, model_version*

Policies:
- `anomaly_signals_delete_locked` [DELETE · roles=public] USING=`false` CHECK=`∅`
- `anomaly_signals_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `anomaly_signals_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`
- `anomaly_signals_update_supervisor` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = anomaly_signals.hive_id) AND ` CHECK=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = anomaly_signals.hive_id) AND `

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
