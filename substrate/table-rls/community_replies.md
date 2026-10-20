---
name: table-rls-community_replies
type: table-rls
source: db:pg_policies+pg_trigger:community_replies
source_sha: 547dec7896425326
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `community_replies` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, post_id*, hive_id*, author_name*, content*, created_at*, auth_uid, is_accepted*, accepted_by, accepted_at

Policies:
- `community_replies_delete` [DELETE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (hive_id IN ( SELECT user_su` CHECK=`∅`
- `community_replies_insert` [INSERT · roles=public] USING=`∅` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)) AND (hive_id IN ( SELECT hm.hive`
- `community_replies_read` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid ` CHECK=`∅`
- `community_replies_modify` [UPDATE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (hive_id IN ( SELECT user_su` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid `

Guard triggers: `trg_bind_submitter_community_reply`, `trg_daily_cap_comm_replies`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
