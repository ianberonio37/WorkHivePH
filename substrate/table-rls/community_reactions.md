---
name: table-rls-community_reactions
type: table-rls
source: db:pg_policies+pg_trigger:community_reactions
source_sha: a894aa9a6c102b44
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `community_reactions` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, post_id*, hive_id*, worker_name*, emoji*, created_at*

Policies:
- `community_reactions_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND ((EXISTS ( SELECT 1 FROM community_posts cp WHERE ((cp.id = community_reactions.post_id) A` CHECK=`∅`
- `community_reactions_read` [SELECT · roles=public] USING=`(((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM community_posts cp WHERE ((cp.id = community_reactions.post_id) A` CHECK=`∅`

Guard triggers: `trg_bind_submitter_community_reaction`, `trg_daily_cap_community_reactions`, `trg_text_caps_community_reactions`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
