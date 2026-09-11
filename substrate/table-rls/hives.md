---
name: table-rls-hives
type: table-rls
source: db:pg_policies+pg_trigger:hives
source_sha: fe1743c335a2c87c
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hives` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, name*, invite_code*, created_by*, created_at, intent*, federated_benchmark_opted_in*, federated_opt_in_at, federated_opt_in_by, preferred_persona*, updated_at*, ai_monthly_cost_cap_usd*

Policies:
- `hives_delete` [DELETE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (id IN ( SELECT hive_members.hive_id FROM hive_members WHERE ((hive_members.auth_uid = aut` CHECK=`∅`
- `hives_insert` [INSERT · roles=public] USING=`∅` CHECK=`(auth.uid() IS NOT NULL)`
- `hives_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `hives_read_member` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`∅`
- `hives_update` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (id IN ( SELECT hive_members.hive_id FROM hive_members WHERE ((hive_members.auth_uid = aut` CHECK=`∅`

Guard triggers: `trg_text_caps_hives`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
