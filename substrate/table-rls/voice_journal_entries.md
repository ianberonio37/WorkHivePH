---
name: table-rls-voice_journal_entries
type: table-rls
source: db:pg_policies+pg_trigger:voice_journal_entries
source_sha: d9c99a130e73f9e9
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `voice_journal_entries` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, auth_uid*, worker_name*, hive_id, transcript*, reply, lang, embedding, meta, created_at*

Policies:
- `voice_journal_delete` [DELETE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))` CHECK=`∅`
- `voice_journal_insert` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))`
- `voice_journal_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))` CHECK=`∅`
- `voice_journal_update` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))` CHECK=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))`

Guard triggers: `trg_bind_submitter_voice_journal`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
