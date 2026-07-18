---
name: table-rls-platform_feedback
type: table-rls
source: db:pg_policies+pg_trigger:platform_feedback
source_sha: f777b2ecb59fa580
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `platform_feedback` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, created_at*, auth_uid, worker_name, hive_id, contact_email, kind*, rating, subject*, body*, page_url, user_agent, status*, priority, labels*, admin_note, resolved_at, is_public*, upvotes*, updated_at*

Policies:
- `feedback admin deletes` [DELETE · roles=public] USING=`is_platform_admin()` CHECK=`∅`
- `feedback anon submit` [INSERT · roles=public] USING=`∅` CHECK=`((is_public IS NOT TRUE) AND (status = 'new'::text) AND (admin_note IS NULL) AND (resolved_at IS NULL))`
- `feedback admin reads all` [SELECT · roles=public] USING=`is_platform_admin()` CHECK=`∅`
- `feedback public reads published` [SELECT · roles=public] USING=`(is_public = true)` CHECK=`∅`
- `platform_feedback_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `feedback admin updates` [UPDATE · roles=public] USING=`is_platform_admin()` CHECK=`is_platform_admin()`

Guard triggers: `trg_bind_platform_feedback_submitter`

**Verdict:** FLAGS: client-writable TRUST/VALUE column(s) ['rating'] + no guard trigger — VALUE-INTEGRITY suspect (self-forgeable unless a BEFORE-trigger guards it or the display sources from a canonical table).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
