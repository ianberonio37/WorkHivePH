-- SL L2 (2026-10-21): A CHANGE TO SHARED STATE LEAVES WHO, WHAT, WHICH AND WHEN - ON EVERY PATH THAT MAKES IT.
--
-- Measured on the 21 L2 pages (.tmp/slw/l2_inventory.py: every insert/update/upsert/delete chain and write RPC the pages
-- make, 213 writes): 18 change a person's own private rows (owner-only RLS), 9 are bookkeeping (a view counter, a
-- notification, a generated code), and many of the changes to state another person reads recorded nothing about who
-- made them - an API key created or revoked, an integration's endpoint changed, a project item reassigned, a report
-- recipient removed, a PM task added to a schedule, an RCM strategy written, a shift plan published, a service
-- request moved on, a provider's service areas changed... The 16 audit
-- triggers that did exist each covered one event (an approval, an amendment, a trash transition), and the per-page
-- writeAuditLog helper only ever covered the path that page takes: the day planner closes a logbook entry with a
-- direct update that wrote no trail at all, while logbook.html's own close did.
--
-- So the trail is written by the DATABASE, once per real change, on every path (a page, an RPC, an offline drain):
--   * audit_shared_change() - one trigger function, attached to each shared table that had no trail, for the events
--     a person decides and NOT the bookkeeping beside them (an API key's call counter, an integration's sync status,
--     a provider's live position: each changes constantly and would bury the trail). It writes add_/change_/remove_
--     <thing>, the thing's own name, and for a change the NAMES of the columns it touched. Values are never copied
--     (an integration's auth token is one of those columns) except a STATE column's new value - a boolean, a status,
--     an availability, an RCM decision - which is one word from a fixed list, and without which the trail could only
--     say "changed an API key (enabled)" where a person needs "turned off an API key". A save that changed nothing
--     writes nothing.
--   * NOT attached where a trail already exists, which the first draft of this migration got wrong three times
--     (measured before applying it): community's pin / flag / visibility / delete / restore each already write their
--     own row from the page, the hive rename writes hive_renamed with from/to, and a second database row for the same
--     change would make the trail say everything twice. Those page rows are fixed where they are instead
--     (community.html: name the post, write only after the database confirmed the change).
--   * NOT attached to marketplace inquiries: an inquiry is a conversation between a buyer and a seller that only the
--     two of them (and a marketplace admin) may read - a row in the hive's trail would show its existence, and its
--     text, to supervisors the inquiry's own policy keeps out. Its reply carries its author and time on the record.
--   * the actor is never taken from the page: wh_bind_audit_actor() (BEFORE INSERT on hive_audit_log) already binds it
--     to the signed-in person's name; a change with no signed-in person reads "the platform".
--   * closing a logbook entry is an event in its own right (close_logbook_entry), whichever page closes it.
--   * a member who deactivates their account leaves a row in each of their hives before their name is erased.
--   * two platform decisions with no hive record who made them on the record itself: a top-up's verified_by (it had
--     verified_at and no verified_by: "when" without "who"), and feedback's triaged_by / triaged_at.
-- Words for every action live in utils.js (WH_AUDIT_ACTIONS / whAuditLabel), read by the hive board and audit-log.html.

create or replace function public.audit_shared_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_new     jsonb := case when tg_op <> 'DELETE' then to_jsonb(new) end;
  v_old     jsonb := case when tg_op <> 'INSERT' then to_jsonb(old) end;
  v_row     jsonb := coalesce(v_new, v_old);
  -- TG_ARGV: [0] the thing's name in the trail ('project item'), [1] the column(s) a person reads as its name ('title';
  -- 'shift_date+shift_window' joins several), [2] the column holding the hive when it is not hive_id
  v_hive    uuid  := nullif(v_row ->> coalesce(tg_argv[2], 'hive_id'), '')::uuid;
  v_thing   text  := coalesce(tg_argv[0], replace(tg_table_name, '_', ' '));
  v_label   text;
  v_changed text[];
  v_to      jsonb := '{}'::jsonb;
begin
  if v_hive is null then
    return null;   -- a row with no hive belongs to no hive's trail
  end if;
  if tg_op = 'UPDATE' then
    select array_agg(k order by k),
           -- a STATE column's new value: one word from a fixed list (or a boolean), never free text
           coalesce(jsonb_object_agg(k, v_new -> k) filter (
             where jsonb_typeof(v_new -> k) = 'boolean' or k in ('status', 'availability', 'decision')), '{}'::jsonb)
      into v_changed, v_to
      from jsonb_object_keys(v_new) k
     where k not in ('updated_at') and (v_new -> k) is distinct from (v_old -> k);
    if v_changed is null then
      return null; -- a save that changed nothing records nothing
    end if;
  end if;
  -- the thing's own name, as a person reads it: whitespace folded, cut at 80 characters with an ellipsis, and NULL
  -- when the row has none (a request scoped by a catalogue item) - never the thing's type standing in for a name
  select nullif(btrim(regexp_replace(string_agg(v_row ->> c.col, ' ' order by c.ord), '\s+', ' ', 'g')), '')
    into v_label
    from unnest(string_to_array(coalesce(tg_argv[1], ''), '+')) with ordinality as c(col, ord)
   where nullif(v_row ->> c.col, '') is not null;
  if length(v_label) > 80 then
    v_label := left(v_label, 79) || '…';
  end if;
  insert into public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  values (v_hive,
          case when auth.uid() is null then 'the platform' else '(bound on insert)' end,   -- wh_bind_audit_actor binds it
          (case tg_op when 'INSERT' then 'add_' when 'UPDATE' then 'change_' else 'remove_' end) || lower(replace(v_thing, ' ', '_')),
          tg_table_name, v_row ->> 'id', v_label,
          case when tg_op <> 'UPDATE' then '{}'::jsonb
               when v_to = '{}'::jsonb then jsonb_build_object('changed', to_jsonb(v_changed))
               else jsonb_build_object('changed', to_jsonb(v_changed), 'to', v_to) end);
  return null;
end
$$;
revoke all on function public.audit_shared_change() from public, anon, authenticated;
comment on function public.audit_shared_change() is
  'SL L2 2026-10-21: one trail row per real change to a shared row (who is bound by wh_bind_audit_actor; changed column NAMES, and a state column''s new value only).';

-- ── where it is attached: only the events that had no trail, only a person's decisions ─────────────────────────────
drop trigger if exists trg_audit_shared_change on public.project_items;
create trigger trg_audit_shared_change after insert or delete or update of title, status, owner_name, notes, wbs_code
  on public.project_items for each row execute function public.audit_shared_change('project item', 'title');
drop trigger if exists trg_audit_shared_change on public.project_links;
create trigger trg_audit_shared_change after insert on public.project_links            -- removal: the trash trigger
  for each row execute function public.audit_shared_change('project link', 'label');
drop trigger if exists trg_audit_shared_change on public.projects;
create trigger trg_audit_shared_change after insert on public.projects                 -- removal: the guard trigger
  for each row execute function public.audit_shared_change('project', 'name');
drop trigger if exists trg_audit_shared_change on public.report_contacts;
create trigger trg_audit_shared_change after insert or update or delete on public.report_contacts
  for each row execute function public.audit_shared_change('report recipient', 'name');
drop trigger if exists trg_audit_shared_change on public.integration_configs;
create trigger trg_audit_shared_change after insert or delete
  or update of system_type, label, endpoint_url, auth_method, sync_freq, auth_token on public.integration_configs
  for each row execute function public.audit_shared_change('integration setting', 'label');
drop trigger if exists trg_audit_shared_change on public.api_keys;
create trigger trg_audit_shared_change after insert or delete or update of enabled, label on public.api_keys
  for each row execute function public.audit_shared_change('API key', 'label');
drop trigger if exists trg_audit_shared_change on public.rcm_strategies;
create trigger trg_audit_shared_change after insert or update of decision, task_text, rationale on public.rcm_strategies
  for each row execute function public.audit_shared_change('RCM strategy', 'task_text');
drop trigger if exists trg_audit_shared_change on public.rcm_fmea_modes;
create trigger trg_audit_shared_change after insert on public.rcm_fmea_modes
  for each row execute function public.audit_shared_change('FMEA failure mode', 'failure_mode');
drop trigger if exists trg_audit_shared_change on public.pm_scope_items;
create trigger trg_audit_shared_change after insert or delete on public.pm_scope_items -- a change: amend_pm_schedule
  for each row execute function public.audit_shared_change('PM task', 'item_text');
drop trigger if exists trg_audit_shared_change on public.shift_plans;
create trigger trg_audit_shared_change after update of status on public.shift_plans    -- '14-22' alone names no shift
  for each row execute function public.audit_shared_change('shift plan', 'shift_date+shift_window');
drop trigger if exists trg_audit_shared_change on public.service_requests;
create trigger trg_audit_shared_change after update of status on public.service_requests
  for each row execute function public.audit_shared_change('service request', 'custom_scope');
drop trigger if exists trg_audit_shared_change on public.service_providers;
create trigger trg_audit_shared_change after insert or update of availability, categories, service_areas, display_name
  on public.service_providers for each row execute function public.audit_shared_change('service provider profile', 'display_name');

-- ── closing a logbook entry, on every path ────────────────────────────────────────────────────────────────────────
create or replace function public.audit_logbook_close()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.hive_id is null then
    return null;   -- a hive-less (solo) entry has no hive trail
  end if;
  insert into public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  values (new.hive_id, case when auth.uid() is null then 'the platform' else '(bound on insert)' end,
          'close_logbook_entry', 'logbook', new.id::text, left(coalesce(nullif(new.machine, ''), '(no machine)'), 120), '{}'::jsonb);
  return null;
end
$$;
revoke all on function public.audit_logbook_close() from public, anon, authenticated;
drop trigger if exists trg_logbook_close_audit on public.logbook;
create trigger trg_logbook_close_audit after update of status on public.logbook
  for each row when (old.status is distinct from 'Closed' and new.status = 'Closed')
  execute function public.audit_logbook_close();

-- ── who decided a top-up (it recorded when, and not who) ─────────────────────────────────────────────────────────────
create or replace function public.stamp_topup_decider()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status is distinct from old.status and new.status in ('verified', 'rejected') and auth.uid() is not null then
    new.verified_by := auth.uid();
    new.verified_at := coalesce(new.verified_at, now());
  end if;
  return new;
end
$$;
revoke all on function public.stamp_topup_decider() from public, anon, authenticated;
drop trigger if exists trg_stamp_topup_decider on public.service_credit_topups;
create trigger trg_stamp_topup_decider before update of status on public.service_credit_topups
  for each row execute function public.stamp_topup_decider();

-- ── who triaged a feedback item ──────────────────────────────────────────────────────────────────────────────────
alter table public.platform_feedback add column if not exists triaged_by uuid;
alter table public.platform_feedback add column if not exists triaged_at timestamptz;
comment on column public.platform_feedback.triaged_by is 'SL L2: the admin whose change last moved this item (status, priority, publicity, note).';
create or replace function public.stamp_feedback_triage()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if auth.uid() is not null and (new.status, new.priority, new.is_public, new.admin_note)
       is distinct from (old.status, old.priority, old.is_public, old.admin_note) then
    new.triaged_by := auth.uid();
    new.triaged_at := now();
  end if;
  return new;
end
$$;
revoke all on function public.stamp_feedback_triage() from public, anon, authenticated;
drop trigger if exists trg_stamp_feedback_triage on public.platform_feedback;
create trigger trg_stamp_feedback_triage before update on public.platform_feedback
  for each row execute function public.stamp_feedback_triage();

-- ── a member who deactivates their account leaves a row in each hive, BEFORE their name is erased ────────────────
-- (wh_bind_audit_actor reads worker_profiles.display_name, which the next statement turns into 'Deleted user'.
--  Operational history keeps the name, as the function's own note says: this is deactivation, not erasure.)
CREATE OR REPLACE FUNCTION public.deactivate_my_account()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  uid uuid := auth.uid();
BEGIN
  IF uid IS NULL THEN
    RAISE EXCEPTION 'not authenticated';
  END IF;

  -- SL L2 (2026-10-21): the hive learns who left and when - a member used to vanish from the roster with nothing in
  -- the trail. Written first, while the actor binding still reads the person's own name.
  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  SELECT hm.hive_id, hm.worker_name, 'deactivated_account', 'worker_profiles', uid::text, hm.worker_name, '{}'::jsonb
    FROM public.hive_members hm
   WHERE hm.auth_uid = uid AND hm.status = 'active';

  -- Anonymize personal data on the identity anchor. Username stays (it is the synthetic-email login
  -- key `username@auth.workhiveph.com`, not real PII); the optional real email + the human display
  -- name are the personal data, and both are erased here.
  UPDATE public.worker_profiles
     SET display_name   = 'Deleted user',
         email          = NULL,
         deactivated_at = now()
   WHERE auth_uid = uid;

  -- Revoke hive access: every membership -> 'deactivated' (validateHiveMembership treats any non-'active'
  -- status as no access, so the deactivated identity is blocked on next load). Operational rows are
  -- intentionally PRESERVED — they carry the hive's maintenance history, not the user's personal data.
  UPDATE public.hive_members
     SET status = 'deactivated'
   WHERE auth_uid = uid;
END;
$function$;
revoke all on function public.deactivate_my_account() from public, anon;
grant execute on function public.deactivate_my_account() to authenticated, service_role;

-- ── a platform decision gets a PLATFORM trail, not the operator's hive's ─────────────────────────────────────────────
-- platform-actions wrote every admin decision - a top-up verified, a listing approved or removed, a seller's identity
-- or certifications verified - into the OPERATOR'S OWN hive trail (hive_audit_log only accepts a hive the writer
-- belongs to). So a decision about one hive's seller sat in an unrelated hive's log, read by that hive's supervisors,
-- under the thing's id as its name - and a readable name there would have shown them another hive's people. A
-- listing's moderated_by was the name the browser sent. The platform's decisions are kept by the platform: written by
-- the database on every path, the actor bound to the signed-in account, read only by platform admins (platform-actions'
-- "Recent decisions").
create table if not exists public.platform_audit_log (
  id          uuid primary key default gen_random_uuid(),
  actor_uid   uuid,
  actor       text not null,
  action      text not null,
  target_type text,
  target_id   text,
  target_name text,
  meta        jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists idx_platform_audit_log_created on public.platform_audit_log (created_at desc, id);
alter table public.platform_audit_log enable row level security;
drop policy if exists platform_audit_log_admin_read on public.platform_audit_log;
create policy platform_audit_log_admin_read on public.platform_audit_log for select to authenticated
  using ((select public.is_marketplace_admin()));
revoke all on public.platform_audit_log from public, anon, authenticated;
grant select on public.platform_audit_log to authenticated;
grant all on public.platform_audit_log to service_role;
comment on table public.platform_audit_log is
  'SL L2 2026-10-21: decisions a platform admin makes (top-ups, listing moderation, seller verification, feedback triage). Written by audit_platform_decision() only; read by platform admins.';

create or replace function public.audit_platform_decision()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid     uuid := auth.uid();
  v_action  text;
  v_name    text;
  v_meta    jsonb := '{}'::jsonb;
  v_changed text[];
begin
  if tg_table_name = 'service_credit_topups' then
    if new.status is not distinct from old.status or new.status not in ('verified', 'rejected') then
      return null;
    end if;
    v_action := case new.status when 'verified' then 'verify_topup' else 'reject_topup' end;
    v_name := 'PHP ' || new.amount::text || ' top-up from '
              || coalesce((select wp.display_name from public.worker_profiles wp where wp.auth_uid = new.payer_auth_uid), 'an account');
    v_meta := jsonb_build_object('account_type', new.account_type);
  elsif tg_table_name = 'marketplace_listings' then
    -- moderation, not a seller's own status change: the console stamps moderated_at on every decision
    if new.moderated_at is not distinct from old.moderated_at then
      return null;
    end if;
    v_action := case when new.status = 'published' then 'approve_listing'
                     when new.status = 'removed' then 'reject_listing' else 'moderate_listing' end;
    v_name := new.title;
    v_meta := jsonb_build_object('to', jsonb_build_object('status', new.status))
              || case when new.moderation_reason is not null then jsonb_build_object('reason', new.moderation_reason) else '{}'::jsonb end;
  elsif tg_table_name = 'marketplace_sellers' then
    if coalesce(new.kyb_verified, false) and not coalesce(old.kyb_verified, false) then
      v_action := 'verify_seller_kyb';
    elsif coalesce(new.cert_verified, false) and not coalesce(old.cert_verified, false) then
      v_action := 'verify_seller_cert';
    else
      return null;
    end if;
    v_name := new.worker_name;
  elsif tg_table_name = 'platform_feedback' then
    select array_agg(c order by c) into v_changed
      from unnest(array['status', 'priority', 'is_public', 'admin_note']) c
     where (to_jsonb(new) -> c) is distinct from (to_jsonb(old) -> c);
    if v_changed is null then
      return null;
    end if;
    v_action := 'triage_feedback';
    v_name := new.subject;
    v_meta := jsonb_build_object('changed', to_jsonb(v_changed),
                                 'to', jsonb_strip_nulls(jsonb_build_object('status', new.status, 'priority', new.priority, 'is_public', new.is_public)));
  else
    return null;
  end if;
  v_name := nullif(btrim(regexp_replace(coalesce(v_name, ''), '\s+', ' ', 'g')), '');
  insert into public.platform_audit_log (actor_uid, actor, action, target_type, target_id, target_name, meta)
  values (v_uid,
          case when v_uid is null then 'the platform'
               else coalesce((select wp.display_name from public.worker_profiles wp where wp.auth_uid = v_uid), '(unknown)') end,
          v_action, tg_table_name, new.id::text,
          case when length(v_name) > 80 then left(v_name, 79) || '…' else v_name end,
          v_meta);
  return null;
end
$$;
revoke all on function public.audit_platform_decision() from public, anon, authenticated;

drop trigger if exists trg_audit_platform_decision on public.service_credit_topups;
create trigger trg_audit_platform_decision after update of status on public.service_credit_topups
  for each row execute function public.audit_platform_decision();
drop trigger if exists trg_audit_platform_decision on public.marketplace_listings;
create trigger trg_audit_platform_decision after update of status, moderated_at on public.marketplace_listings
  for each row execute function public.audit_platform_decision();
drop trigger if exists trg_audit_platform_decision on public.marketplace_sellers;
create trigger trg_audit_platform_decision after update of kyb_verified, cert_verified on public.marketplace_sellers
  for each row execute function public.audit_platform_decision();
drop trigger if exists trg_audit_platform_decision on public.platform_feedback;
create trigger trg_audit_platform_decision after update of status, priority, is_public, admin_note on public.platform_feedback
  for each row execute function public.audit_platform_decision();

-- the moderator is the signed-in account, never the name the browser sent
create or replace function public.bind_listing_moderator()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.moderated_at is distinct from old.moderated_at and auth.uid() is not null then
    new.moderated_by := coalesce((select wp.display_name from public.worker_profiles wp where wp.auth_uid = auth.uid()),
                                 new.moderated_by);
  end if;
  return new;
end
$$;
revoke all on function public.bind_listing_moderator() from public, anon, authenticated;
drop trigger if exists trg_bind_listing_moderator on public.marketplace_listings;
create trigger trg_bind_listing_moderator before update of moderated_at on public.marketplace_listings
  for each row execute function public.bind_listing_moderator();

-- ── a published plan names who released it: the signed-in account, never the name the browser sent ──────────────────
-- shift-brain's publishPlan() sets published_by to the page's own WORKER_NAME, and the crew reads the plan as
-- "released under your name" - the one claim on that record a person acts on, and the one the page could set to anyone.
create or replace function public.bind_shift_plan_publisher()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status = 'published' and old.status is distinct from 'published' and auth.uid() is not null then
    new.published_by := coalesce(
      (select wp.display_name from public.worker_profiles wp where wp.auth_uid = auth.uid()),
      (select hm.worker_name from public.hive_members hm
        where hm.auth_uid = auth.uid() and hm.hive_id = new.hive_id and hm.status = 'active' limit 1),
      new.published_by);
    new.published_at := coalesce(new.published_at, now());
  end if;
  return new;
end
$$;
revoke all on function public.bind_shift_plan_publisher() from public, anon, authenticated;
drop trigger if exists trg_bind_shift_plan_publisher on public.shift_plans;
create trigger trg_bind_shift_plan_publisher before update of status on public.shift_plans
  for each row execute function public.bind_shift_plan_publisher();

-- ── the hive's focus: a supervisor's decision with no trail ─────────────────────────────────────────────────────────
-- hive.html's focus picker writes hives.intent (the hive's primary goal) and stamps captured_by with the page's own
-- name; nothing reached the hive's trail. The generic trail is attached to that column ONLY - a rename already writes
-- hive_renamed (with from/to) from the page's one rename path, and a second row for it would say it twice.
drop trigger if exists trg_audit_shared_change on public.hives;
create trigger trg_audit_shared_change after update of intent on public.hives
  for each row execute function public.audit_shared_change('hive setting', 'name', 'id');
