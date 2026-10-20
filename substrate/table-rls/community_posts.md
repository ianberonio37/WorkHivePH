---
name: table-rls-community_posts
type: table-rls
source: db:pg_policies+pg_trigger:community_posts
source_sha: d546ac0852cc6583
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `community_posts` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id*, author_name*, content*, category*, pinned*, flagged*, created_at*, auth_uid, public*, edited_at, deleted_at, mentions*, updated_at*, deleted_by

Policies:
- `community_posts_delete` [DELETE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (EXISTS ( SELECT 1 FROM hive` CHECK=`∅`
- `community_posts_insert` [INSERT · roles=public] USING=`∅` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (auth_uid IS NULL)) AND (hiv`
- `community_posts_hides_deleted` [SELECT · roles=public] USING=`((deleted_at IS NULL) OR ( SELECT wh_trash_scope() AS wh_trash_scope))` CHECK=`∅`
- `community_posts_read` [SELECT · roles=public] USING=`(((public = true) AND (flagged = false)) OR ((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_` CHECK=`∅`
- `community_posts_update` [UPDATE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (EXISTS ( SELECT 1 FROM hive` CHECK=`∅`

Guard triggers: `trg_bind_submitter_community_post`, `trg_daily_cap_comm_posts`, `trg_guard_community_announcement`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
