---
name: table-rls-hive_members
type: table-rls
source: db:pg_policies+pg_trigger:hive_members
source_sha: 9d22d09819223b6f
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_members` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, worker_name*, role*, joined_at, status*, auth_uid

Policies:
- `hive_members_delete` [DELETE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()) AND (status <> 'kicked'::text))` CHECK=`∅`
- `hive_members_insert` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()) AND (role = 'supervisor'::text) AND (status = 'active'::text) AND `
- `hive_members_read_scoped` [SELECT · roles=public] USING=`((auth_uid = auth.uid()) OR (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`∅`
- `hive_members_update` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_supervisor_hive_ids() AS user_supervisor_hive_ids)))` CHECK=`∅`

Guard triggers: `trg_text_caps_hive_members`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
