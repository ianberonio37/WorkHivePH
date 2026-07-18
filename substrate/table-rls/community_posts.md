---
name: table-rls-community_posts
type: table-rls
source: db:pg_policies+pg_trigger:community_posts
source_sha: 4e976a8bc0153875
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `community_posts` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id*, author_name*, content*, category*, pinned*, flagged*, created_at*, auth_uid, public*, edited_at, deleted_at, mentions*, updated_at*

Policies:
- `community_posts_delete` [DELETE · roles=public] USING=`((auth.uid() IS NOT NULL) AND ((auth_uid = auth.uid()) OR (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = c` CHECK=`∅`
- `community_posts_insert` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND ((auth_uid = auth.uid()) OR (auth_uid IS NULL)) AND (hive_id IN ( SELECT hm.hive_id FROM h`
- `community_posts_read` [SELECT · roles=public] USING=`(((public = true) AND (flagged = false)) OR ((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_memb` CHECK=`∅`
- `community_posts_update` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND ((auth_uid = auth.uid()) OR (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = c` CHECK=`∅`

Guard triggers: `trg_bind_submitter_community_post`, `trg_daily_cap_comm_posts`, `trg_guard_community_announcement`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
