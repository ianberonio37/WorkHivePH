-- T422 (orphaned child after parent delete) — the REAL fix, found 2026-09-01.
-- The walk had verified "every child table of hives carries ON DELETE CASCADE" over the FK-BEARING
-- relations (63 CASCADE + 15 by-design SET NULL) and concluded "no orphaned rows". The claim was
-- incomplete: THIRTY-THREE public tables carry a hive_id column with NO foreign key to hives at all,
-- so a hive delete leaves true orphans — and live orphans already existed: analytics_events 1,834,
-- anomaly_alerts 20, kb_documents 3, dialog_state 3 (dangling hive_ids pointing at deleted hives,
-- invisible to hive-scoped RLS yet still reachable by service-role/DEFINER paths).
--
-- Disposition follows the schema's own established pattern:
--   • ON DELETE CASCADE — hive-owned structure/content/state dies with the hive
--     (the existing 63: asset_nodes, hive_members, knowledge, caches, agent memory …).
--   • ON DELETE SET NULL — worker-owned records, money/audit records and platform telemetry
--     survive detached (the existing 15: logbook, voice_journal, resume, marketplace_*, ai_cost_log …).
--
-- Cleanup first (an FK cannot be added over dangling rows): CASCADE-class dangling rows are deleted
-- (they would have been cascaded had the FK existed); SET-NULL-class dangling rows are nulled.

-- ── cleanup ──────────────────────────────────────────────────────────────
delete from public.kb_documents      x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.anomaly_alerts    x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.dialog_state      x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
update public.analytics_events       x set hive_id = null where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
-- belt-and-braces for the remaining 29 (0 dangling measured today, but a reseed may drift):
update public.pm_completions         x set hive_id = null where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
update public.engineering_calcs      x set hive_id = null where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
update public.service_payments       x set hive_id = null where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
update public.credit_reservations    x set hive_id = null where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
update public.conversation_analytics x set hive_id = null where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
update public.wh_traces              x set hive_id = null where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id::uuid);
update public.tts_quality_log        x set hive_id = null where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
update public.automation_log         x set hive_id = null where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
update public.platform_feedback      x set hive_id = null where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.ai_user_rate_limits       x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id::uuid);
delete from public.alert_dismissals          x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.analytics_snapshots       x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.community_post_xp_awards  x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.community_reaction_xp_awards x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.community_reactions       x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.community_replies         x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.community_reply_xp_awards x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.embedding_outbox          x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.external_sync             x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.inventory_items           x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.kb_documents              x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.offline_snapshot_cache    x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.pm_scope_items            x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.project_change_orders     x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.project_items             x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.project_knowledge         x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.project_links             x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.project_progress_logs     x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.project_roles             x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);
delete from public.projects                  x where x.hive_id is not null and not exists (select 1 from public.hives h where h.id = x.hive_id);

-- ── type repair: two tables stored hive_id as TEXT (a schema smell this migration also fixes);
--    both verified 100% uuid-shaped before the cast (0 non-conforming values).
--    wh_traces_hive_read references hive_id, and Postgres refuses ALTER TYPE under a policy —
--    so it is dropped and recreated FAITHFULLY (same claim source) with the uuid cast added. ──
drop policy if exists wh_traces_hive_read on public.wh_traces;
alter table public.wh_traces           alter column hive_id type uuid using nullif(hive_id, '')::uuid;
alter table public.ai_user_rate_limits alter column hive_id type uuid using nullif(hive_id, '')::uuid;
create policy wh_traces_hive_read on public.wh_traces for select to authenticated
  using (hive_id = (((current_setting('request.jwt.claims'::text, true))::json ->> 'hive_id'::text))::uuid);

-- ── CASCADE: hive-owned structure / content / state ──────────────────────
alter table public.projects                     add constraint projects_hive_id_fkey                     foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.project_items                add constraint project_items_hive_id_fkey                foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.project_links                add constraint project_links_hive_id_fkey                foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.project_progress_logs        add constraint project_progress_logs_hive_id_fkey        foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.project_roles                add constraint project_roles_hive_id_fkey                foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.project_change_orders        add constraint project_change_orders_hive_id_fkey        foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.project_knowledge            add constraint project_knowledge_hive_id_fkey            foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.pm_scope_items               add constraint pm_scope_items_hive_id_fkey               foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.inventory_items              add constraint inventory_items_hive_id_fkey              foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.kb_documents                 add constraint kb_documents_hive_id_fkey                 foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.community_replies            add constraint community_replies_hive_id_fkey            foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.community_reactions          add constraint community_reactions_hive_id_fkey          foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.community_post_xp_awards     add constraint community_post_xp_awards_hive_id_fkey     foreign key (hive_id) references public.hives(id) on delete cascade;
-- EXEMPT: community_reply_xp_awards deliberately carries NO foreign keys (community_xp_ledger gate
-- invariant: replies HARD-delete, so ANY cascade would erase the award row at the instant the
-- reversal trigger needs to read it, silently re-opening the reply-XP farm). The 2026-09-02 full
-- board caught this stanza violating that invariant; the FK was dropped live and this line retired.
-- alter table public.community_reply_xp_awards    add constraint community_reply_xp_awards_hive_id_fkey    foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.community_reaction_xp_awards add constraint community_reaction_xp_awards_hive_id_fkey foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.dialog_state                 add constraint dialog_state_hive_id_fkey                 foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.offline_snapshot_cache       add constraint offline_snapshot_cache_hive_id_fkey       foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.embedding_outbox             add constraint embedding_outbox_hive_id_fkey             foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.alert_dismissals             add constraint alert_dismissals_hive_id_fkey             foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.anomaly_alerts               add constraint anomaly_alerts_hive_id_fkey               foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.analytics_snapshots          add constraint analytics_snapshots_hive_id_fkey          foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.ai_user_rate_limits          add constraint ai_user_rate_limits_hive_id_fkey          foreign key (hive_id) references public.hives(id) on delete cascade;
alter table public.external_sync                add constraint external_sync_hive_id_fkey                foreign key (hive_id) references public.hives(id) on delete cascade;

-- ── SET NULL: worker-owned / money-audit / platform telemetry survive detached ──
alter table public.pm_completions        add constraint pm_completions_hive_id_fkey        foreign key (hive_id) references public.hives(id) on delete set null;
alter table public.engineering_calcs     add constraint engineering_calcs_hive_id_fkey     foreign key (hive_id) references public.hives(id) on delete set null;
alter table public.service_payments      add constraint service_payments_hive_id_fkey      foreign key (hive_id) references public.hives(id) on delete set null;
alter table public.credit_reservations   add constraint credit_reservations_hive_id_fkey   foreign key (hive_id) references public.hives(id) on delete set null;
alter table public.analytics_events      add constraint analytics_events_hive_id_fkey      foreign key (hive_id) references public.hives(id) on delete set null;
alter table public.conversation_analytics add constraint conversation_analytics_hive_id_fkey foreign key (hive_id) references public.hives(id) on delete set null;
alter table public.wh_traces             add constraint wh_traces_hive_id_fkey             foreign key (hive_id) references public.hives(id) on delete set null;
alter table public.tts_quality_log       add constraint tts_quality_log_hive_id_fkey       foreign key (hive_id) references public.hives(id) on delete set null;
alter table public.automation_log        add constraint automation_log_hive_id_fkey        foreign key (hive_id) references public.hives(id) on delete set null;
alter table public.platform_feedback     add constraint platform_feedback_hive_id_fkey     foreign key (hive_id) references public.hives(id) on delete set null;
