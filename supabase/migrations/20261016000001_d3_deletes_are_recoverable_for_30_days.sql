-- D3 (Ian, 2026-10-16: "30-day recoverable"): what a page deletes stays recoverable for 30 days.
--
-- Seven pages deleted rows outright, so a mistaken tap lost the row and everything that hung off it:
--   logbook.html         logbook          ("This cannot be undone")
--   logbook.html         asset_nodes      (cascades FMEA modes, Weibull fits, P-F intervals, sensor readings)
--   inventory.html       inventory_items  (cascades the stock ledger)
--   dayplanner.html      schedule_items
--   pm-scheduler.html    pm_assets        (cascades PM completions and scope)
--   project-manager.html project_links, project_roles
-- A delete now stamps deleted_at instead. The row and everything under it survive; it disappears from every
-- read; the person can restore it from an Undo toast or the "Recently deleted" list; the daily retention job
-- purges it after the hive's soft_delete_retention_days (30 by default - the privacy policy's 30 days).
--
-- How each part works:
-- * HIDDEN EVERYWHERE BY ONE RULE. A restrictive SELECT policy per table hides deleted rows, so every page
--   read, every invoker view (v_logbook_truth, v_asset_truth, ...) and every invoker RPC inherits it. Readers
--   that bypass RLS (security-definer functions, service-role edge functions) filter explicitly - those are
--   swept in 20261016000002.
-- * THE PERSON'S OWN PERMISSIONS, UNCHANGED. Trash, restore and the list run as the caller (security
--   invoker), so each table's existing UPDATE policy decides who may trash or restore a row - the same people
--   who could delete it (every one of these tables grants UPDATE and DELETE to the same predicate). The hide
--   rule is relaxed only inside those three functions, by a transaction-local flag (workhive.trash_scope):
--   Postgres checks an UPDATE's new row against the SELECT policies, so stamping deleted_at under a policy
--   that hides deleted rows is otherwise refused ("new row violates row-level security policy" - probed).
-- * GUARDS AND AUDITS FIRE AT THE PERSON'S ACTION. Trashing or restoring signed-off work needs a supervisor,
--   exactly as deleting it did; the audit log records delete and recover when they happen, and purge when the
--   retention job removes the row; XP a logbook entry earned is taken back on delete and given back on
--   restore.
-- * A NAME THAT IS STILL TAKEN SAYS WHERE IT IS. The unique keys stay whole (two bulk imports upsert on them),
--   so a deleted asset still holds its tag and a deleted part its part number. Creating another with the same
--   tag says it is in Recently deleted. A project link or role is just a pairing with nothing under it, so
--   re-adding one simply replaces the deleted copy.
-- * COMMUNITY POSTS JOIN THE SAME RULE. They were already soft-deleted, but only the page hid them: the read
--   policy lets ANYONE read a public post, so a deleted public post stayed readable through the API for its 30
--   days, and after the page's 10-second Undo nothing could bring one back. They now have the hide policy and
--   a Recently deleted list like the rest.
-- Forward-only and idempotent.

-- ── 1. The columns ──────────────────────────────────────────────────────────────────────────────────────────
do $$
declare t text;
begin
  foreach t in array array['logbook','inventory_items','schedule_items','asset_nodes','pm_assets','project_links','project_roles','community_posts']
  loop
    execute format('alter table public.%I add column if not exists deleted_at timestamptz, add column if not exists deleted_by uuid', t);
    execute format('create index if not exists %I on public.%I (deleted_at) where deleted_at is not null', 'idx_' || t || '_deleted_at', t);
    execute format('comment on column public.%I.deleted_at is %L', t,
      'D3 (2026-10-16): when this row was deleted. A deleted row is hidden from every read (policy ' || t
      || '_hides_deleted), restorable through wh_restore, and purged by hard_delete_expired_soft_deletes after '
      || 'the hive''s soft_delete_retention_days (30 by default).');
    execute format('comment on column public.%I.deleted_by is %L', t, 'D3: auth uid of the person who deleted this row.');
  end loop;
end $$;

-- ── 2. The hide rule, and the flag that relaxes it inside the trash functions ───────────────────────────────
create or replace function public.wh_trash_scope()
returns boolean
language sql
stable
set search_path = ''
as $$
  select coalesce(current_setting('workhive.trash_scope', true), '') = 'on'
$$;
comment on function public.wh_trash_scope() is
  'D3: true only inside wh_trash / wh_restore / wh_recently_deleted, which set workhive.trash_scope for their own '
  'transaction. The <table>_hides_deleted policies let deleted rows through only then.';

do $$
declare t text;
begin
  foreach t in array array['logbook','inventory_items','schedule_items','asset_nodes','pm_assets','project_links','project_roles','community_posts']
  loop
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = t || '_hides_deleted') then
      execute format(
        'create policy %I on public.%I as restrictive for select to public using (deleted_at is null or (select public.wh_trash_scope()))',
        t || '_hides_deleted', t);
    end if;
  end loop;
end $$;

-- ── 3. Trash, restore, and the Recently deleted list ────────────────────────────────────────────────────────
-- The tables a page may trash, and the type of each one's id.
create or replace function public._wh_trash_id_type(p_table text)
returns text
language sql
immutable
set search_path = ''
as $$
  select case p_table
    when 'logbook'         then 'text'
    when 'inventory_items' then 'text'
    when 'schedule_items'  then 'text'
    when 'asset_nodes'     then 'uuid'
    when 'pm_assets'       then 'uuid'
    when 'project_links'   then 'uuid'
    when 'project_roles'   then 'uuid'
    when 'community_posts' then 'uuid'
  end
$$;

-- Days a deleted row is kept before the purge: the hive's own setting, else 30. Definer, because
-- hive_retention_config is not readable by members; it returns one number and nothing else.
create or replace function public.wh_retention_days(p_hive uuid)
returns integer
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce((select c.soft_delete_retention_days::int from public.hive_retention_config c where c.hive_id = p_hive), 30)
$$;
revoke all on function public.wh_retention_days(uuid) from public, anon;
grant execute on function public.wh_retention_days(uuid) to authenticated;

create or replace function public.wh_trash(p_table text, p_id text)
returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  v_type text := public._wh_trash_id_type(p_table);
  -- clock_timestamp, not now(): the XP trigger hands back exactly what the delete stamped at this instant, and
  -- now() is one instant for a whole transaction.
  v_at   timestamptz := clock_timestamp();
  v_hive uuid;
  v_seen timestamptz;
  v_found boolean;
  v_n    integer;
begin
  if v_type is null then
    raise exception 'Nothing can be deleted from "%" this way.', p_table using errcode = '22023';
  end if;
  if auth.uid() is null then
    raise exception 'Sign in to delete.' using errcode = '42501';
  end if;

  perform set_config('workhive.trash_scope', 'on', true);
  execute format(
    'update public.%I set deleted_at = $1, deleted_by = auth.uid() where id = $2::%s and deleted_at is null returning %s',
    p_table, v_type, case when p_table = 'schedule_items' then 'null::uuid' else 'hive_id' end)
    into v_hive using v_at, p_id;
  get diagnostics v_n = row_count;

  if v_n = 0 then
    -- Say which of the three it was: gone, already deleted, or not this person's to delete.
    execute format('select true, deleted_at from public.%I where id = $1::%s', p_table, v_type)
      into v_found, v_seen using p_id;
    perform set_config('workhive.trash_scope', '', true);
    if v_found is null then
      raise exception 'It is no longer there - it may have been deleted already.' using errcode = 'P0001';
    elsif v_seen is not null then
      raise exception 'It is already in Recently deleted.' using errcode = 'P0001';
    else
      raise exception 'Your account cannot delete this one, so nothing was deleted.' using errcode = '42501';
    end if;
  end if;

  perform set_config('workhive.trash_scope', '', true);
  return jsonb_build_object(
    'table', p_table, 'id', p_id, 'deleted_at', v_at,
    'purge_after', v_at + make_interval(days => public.wh_retention_days(v_hive)));
end;
$$;
comment on function public.wh_trash(text, text) is
  'D3: delete a row recoverably - stamps deleted_at under the caller''s own UPDATE permission. Returns when it '
  'will be purged. Errors: P0001 already gone / already deleted, 42501 not the caller''s to delete.';

create or replace function public.wh_restore(p_table text, p_id text)
returns jsonb
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  v_type text := public._wh_trash_id_type(p_table);
  v_found boolean;
  v_seen timestamptz;
  v_n    integer;
begin
  if v_type is null then
    raise exception 'Nothing can be restored to "%" this way.', p_table using errcode = '22023';
  end if;
  if auth.uid() is null then
    raise exception 'Sign in to restore.' using errcode = '42501';
  end if;

  perform set_config('workhive.trash_scope', 'on', true);
  execute format(
    'update public.%I set deleted_at = null, deleted_by = null where id = $1::%s and deleted_at is not null',
    p_table, v_type) using p_id;
  get diagnostics v_n = row_count;

  if v_n = 0 then
    execute format('select true, deleted_at from public.%I where id = $1::%s', p_table, v_type)
      into v_found, v_seen using p_id;
    perform set_config('workhive.trash_scope', '', true);
    if v_found is null then
      raise exception 'It can no longer be restored - it was removed for good after its 30 days.' using errcode = 'P0001';
    elsif v_seen is null then
      raise exception 'It is already back.' using errcode = 'P0001';
    else
      raise exception 'Your account cannot restore this one, so nothing was restored.' using errcode = '42501';
    end if;
  end if;

  perform set_config('workhive.trash_scope', '', true);
  return jsonb_build_object('table', p_table, 'id', p_id, 'restored', true);
end;
$$;
comment on function public.wh_restore(text, text) is
  'D3: bring back a deleted row under the caller''s own UPDATE permission. Errors: P0001 purged / already back, '
  '42501 not the caller''s to restore.';

-- What the caller can bring back, still inside the retention window: their own rows, rows they deleted, and - for a
-- supervisor - their hive's rows (a logbook entry only its author may restore, so only the author sees it). Never a
-- teammate's deleted post or entry: being able to READ a row before it was deleted is not a reason to keep showing
-- it after its owner deleted it. p_table narrows it to one table; p_hive to one hive (personal rows - a day plan, a
-- solo logbook - always count as the caller's).
create or replace function public.wh_recently_deleted(p_table text default null, p_hive uuid default null)
returns table (
  source_table   text,
  id             text,
  label          text,
  detail         text,
  hive_id        uuid,
  deleted_at     timestamptz,
  deleted_by_me  boolean,
  deleted_by_name text,
  purge_after    timestamptz
)
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  if auth.uid() is null then
    raise exception 'Sign in to see what was deleted.' using errcode = '42501';
  end if;
  if p_table is not null and public._wh_trash_id_type(p_table) is null then
    raise exception 'There is no Recently deleted list for "%".', p_table using errcode = '22023';
  end if;

  perform set_config('workhive.trash_scope', 'on', true);
  return query
  with d as (
    select 'logbook'::text t, l.id::text i,
           coalesce(nullif(l.machine, ''), 'Logbook entry') lb,
           left(coalesce(l.problem, ''), 120) dt, l.hive_id h, l.deleted_at da, l.deleted_by db
      from public.logbook l
     where l.deleted_at is not null and (p_table is null or p_table = 'logbook')
       and (l.auth_uid = auth.uid() or l.deleted_by = auth.uid())                 -- only its author may restore it
       and (p_hive is null or l.hive_id = p_hive or (l.hive_id is null and l.auth_uid = auth.uid()))
    union all
    select 'inventory_items', i.id::text, coalesce(nullif(i.part_name, ''), i.part_number, 'Part'),
           concat_ws(' · ', i.part_number, i.category), i.hive_id, i.deleted_at, i.deleted_by
      from public.inventory_items i
     where i.deleted_at is not null and (p_table is null or p_table = 'inventory_items')
       and (i.auth_uid = auth.uid() or i.deleted_by = auth.uid() or i.hive_id in (select public.user_supervisor_hive_ids()))
       and (p_hive is null or i.hive_id = p_hive or (i.hive_id is null and i.auth_uid = auth.uid()))
    union all
    select 'schedule_items', s.id::text, coalesce(nullif(s.title, ''), 'Plan item'),
           concat_ws(' · ', s.date, s.start_time), null::uuid, s.deleted_at, s.deleted_by
      from public.schedule_items s
     where s.deleted_at is not null and (p_table is null or p_table = 'schedule_items')
    union all
    select 'asset_nodes', a.id::text, coalesce(nullif(a.tag, ''), a.name, 'Asset'),
           case when a.tag is not null and a.name is not null then a.name else '' end, a.hive_id, a.deleted_at, a.deleted_by
      from public.asset_nodes a
     where a.deleted_at is not null and (p_table is null or p_table = 'asset_nodes')
       and (a.auth_uid = auth.uid() or a.deleted_by = auth.uid() or a.hive_id in (select public.user_supervisor_hive_ids()))
       and (p_hive is null or a.hive_id = p_hive or (a.hive_id is null and a.auth_uid = auth.uid()))
    union all
    select 'pm_assets', p.id::text, coalesce(nullif(p.asset_name, ''), 'PM asset'), coalesce(p.category, ''),
           p.hive_id, p.deleted_at, p.deleted_by
      from public.pm_assets p
     where p.deleted_at is not null and (p_table is null or p_table = 'pm_assets')
       and (p.auth_uid = auth.uid() or p.deleted_by = auth.uid() or p.hive_id in (select public.user_supervisor_hive_ids()))
       and (p_hive is null or p.hive_id = p_hive or (p.hive_id is null and p.auth_uid = auth.uid()))
    union all
    select 'project_links', k.id::text, coalesce(nullif(k.label, ''), k.link_type, 'Link'),
           concat_ws(' · ', pr.project_code, k.link_type), k.hive_id, k.deleted_at, k.deleted_by
      from public.project_links k
      left join public.projects pr on pr.id = k.project_id
     where k.deleted_at is not null and (p_table is null or p_table = 'project_links')
       and (k.deleted_by = auth.uid() or k.hive_id in (select public.user_supervisor_hive_ids()))
       and (p_hive is null or k.hive_id = p_hive)
    union all
    select 'project_roles', r.id::text, concat_ws(' · ', r.worker_name, r.role),
           coalesce(pr.project_code, ''), r.hive_id, r.deleted_at, r.deleted_by
      from public.project_roles r
      left join public.projects pr on pr.id = r.project_id
     where r.deleted_at is not null and (p_table is null or p_table = 'project_roles')
       and (p_hive is null or r.hive_id = p_hive)
    union all
    select 'community_posts', c.id::text, left(coalesce(nullif(c.content, ''), 'Post'), 80),
           coalesce(c.category, ''), c.hive_id, c.deleted_at, c.deleted_by
      from public.community_posts c
     where c.deleted_at is not null and (p_table is null or p_table = 'community_posts')
       and (c.auth_uid = auth.uid() or c.deleted_by = auth.uid() or c.hive_id in (select public.user_supervisor_hive_ids()))
       and (p_hive is null or c.hive_id = p_hive)
  )
  select d.t, d.i, d.lb, d.dt, d.h, d.da, (d.db = auth.uid()),
         (select hm.worker_name from public.hive_members hm
           where hm.auth_uid = d.db and (d.h is null or hm.hive_id = d.h) limit 1),
         d.da + make_interval(days => public.wh_retention_days(d.h))
    from d
   order by d.da desc
   limit 200;
  perform set_config('workhive.trash_scope', '', true);
end;
$$;
comment on function public.wh_recently_deleted(text, uuid) is
  'D3: the Recently deleted list - deleted rows the caller can read, newest first, with who deleted each and '
  'when it will be purged. Runs as the caller, so it shows nothing the caller could not have seen before.';

revoke all on function public.wh_trash(text, text) from public, anon;
revoke all on function public.wh_restore(text, text) from public, anon;
revoke all on function public.wh_recently_deleted(text, uuid) from public, anon;
grant execute on function public.wh_trash(text, text) to authenticated;
grant execute on function public.wh_restore(text, text) to authenticated;
grant execute on function public.wh_recently_deleted(text, uuid) to authenticated;

-- ── 4. Trashing or restoring signed-off work needs a supervisor, as deleting it did ─────────────────────────
CREATE OR REPLACE FUNCTION public.wh_guard_supervisor_approval()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  jnew jsonb := CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE to_jsonb(NEW) END;
  jold jsonb := CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE to_jsonb(OLD) END;
  h uuid := (COALESCE(jnew, jold) ->> 'hive_id')::uuid;
  sup_states text[] := ARRAY['approved','assigned','verified','rejected'];
  -- The states only a REVIEWER may put a submission into. Approving and refusing are the same
  -- authority exercised two ways; the guard used to recognise only the first.
  reviewer_states text[] := ARRAY['approved','rejected'];
  privileged boolean := false;
BEGIN
  IF auth.uid() IS NULL THEN                       -- backend/service-role: RLS already authorized
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
  END IF;

  IF TG_OP = 'INSERT' THEN
    privileged := (jnew ->> 'approved_at') IS NOT NULL
               OR (jnew ->> 'approved_by') IS NOT NULL
               OR (jnew ->> 'status') = ANY (reviewer_states)
               OR (jnew ->> 'wo_state') = ANY (sup_states);
  ELSIF TG_OP = 'UPDATE' THEN
    privileged := ((jnew ->> 'approved_at') IS DISTINCT FROM (jold ->> 'approved_at'))
               OR ((jnew ->> 'approved_by') IS DISTINCT FROM (jold ->> 'approved_by'))
               OR ( (jnew ->> 'status') IS DISTINCT FROM (jold ->> 'status')
                    AND ( (jnew ->> 'status') = ANY (reviewer_states)
                          OR (jold ->> 'status') = ANY (reviewer_states) ) )
               -- The reviewer's written verdict is theirs to write.
               OR ((jnew ->> 'rejection_reason') IS DISTINCT FROM (jold ->> 'rejection_reason'))
               OR ( (jnew ->> 'wo_state') IS DISTINCT FROM (jold ->> 'wo_state')
                    AND (jnew ->> 'wo_state') = ANY (sup_states) )
               -- D3 (2026-10-16): a delete is now an UPDATE stamping deleted_at, so the DELETE branch below
               -- no longer sees it. Trashing - or restoring - signed-off work is the same authority.
               OR ( (jnew ->> 'deleted_at') IS DISTINCT FROM (jold ->> 'deleted_at')
                    AND ( (jold ->> 'approved_at') IS NOT NULL
                          OR (jold ->> 'status') = 'approved'
                          OR (jold ->> 'wo_state') IN ('approved','verified') ) );
  ELSE  -- DELETE: protect signed-off work from member deletion (data loss).
    privileged := (jold ->> 'approved_at') IS NOT NULL
               OR (jold ->> 'status') = 'approved'
               OR (jold ->> 'wo_state') IN ('approved','verified');
  END IF;

  IF privileged AND h IS NOT NULL AND h NOT IN (SELECT public.user_supervisor_hive_ids()) THEN
    RAISE EXCEPTION 'Supervisor role required to approve/assign/verify or remove signed-off work (user %, hive %)', auth.uid(), h
      USING ERRCODE = '42501';
  END IF;

  RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$function$;

-- ── 5. The audit log records delete and recover when they happen ────────────────────────────────────────────
create or replace function public.audit_trash_transition()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  j      jsonb := to_jsonb(NEW);
  v_hive uuid  := nullif(j ->> 'hive_id', '')::uuid;
  v_actor text;
  v_name  text;
  v_kind  text;
begin
  if (NEW.deleted_at is null) = (OLD.deleted_at is null) then return NEW; end if;   -- only live <-> deleted
  if v_hive is null then return NEW; end if;     -- personal rows: no hive audience (hive_id is NOT NULL there)

  -- The hive's audit feed already names these deletes (hive.html AUDIT labels); recover_* is new.
  v_kind := case
              when NEW.deleted_at is not null and TG_TABLE_NAME = 'project_roles' then 'remove_project_role'
              when NEW.deleted_at is not null then 'delete_'
              else 'recover_' end
         || case when NEW.deleted_at is not null and TG_TABLE_NAME = 'project_roles' then ''
            else case TG_TABLE_NAME
              when 'logbook'         then 'logbook_entry'
              when 'inventory_items' then 'inventory_item'
              when 'asset_nodes'     then 'asset_node'
              when 'pm_assets'       then 'pm_asset'
              when 'project_links'   then 'project_link'
              when 'project_roles'   then 'project_role'
              else TG_TABLE_NAME end end;
  v_name := coalesce(nullif(j ->> 'tag', ''), nullif(j ->> 'asset_name', ''), nullif(j ->> 'part_name', ''),
                     nullif(j ->> 'machine', ''), nullif(j ->> 'label', ''),
                     nullif(concat_ws(' · ', j ->> 'worker_name', j ->> 'role'), ''), j ->> 'name', '(unnamed)');

  select hm.worker_name into v_actor
    from public.hive_members hm
   where hm.auth_uid = auth.uid() and hm.hive_id = v_hive
   limit 1;

  insert into public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  values (
    v_hive,
    coalesce(v_actor, j ->> 'worker_name', 'unknown'),
    v_kind,
    TG_TABLE_NAME,
    j ->> 'id',
    v_name,
    jsonb_build_object(
      'status_was',        j ->> 'status',
      'recoverable_until', case when NEW.deleted_at is not null
                                then NEW.deleted_at + make_interval(days => public.wh_retention_days(v_hive)) end,
      'source',            'db_trigger'));
  return NEW;
end;
$$;

do $$
declare t text;
begin
  foreach t in array array['logbook','inventory_items','asset_nodes','pm_assets','project_links','project_roles']
  loop
    execute format('drop trigger if exists trg_audit_trash_transition on public.%I', t);
    execute format('create trigger trg_audit_trash_transition after update of deleted_at on public.%I '
                   'for each row execute function public.audit_trash_transition()', t);
  end loop;
end $$;

-- ── 6. XP a logbook entry earned is taken back on delete and given back on restore ──────────────────────────
-- The purge's own AFTER DELETE reversal (trg_logbook_xp_reverse) then finds nothing left to reverse.
create or replace function public.trg_logbook_xp_on_trash()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare r record;
begin
  if (NEW.deleted_at is null) = (OLD.deleted_at is null) then return NEW; end if;   -- only live <-> deleted

  if NEW.deleted_at is not null then
    for r in
      select id, worker_name, achievement_id, xp_earned, source_action
        from public.achievement_xp_log
       where source_id = NEW.id::text and reversed_at is null and xp_earned > 0
       for update
    loop
      update public.worker_achievements
         set xp_total = greatest(0, xp_total - r.xp_earned)
       where worker_name = r.worker_name and achievement_id = r.achievement_id;
      update public.achievement_xp_log set reversed_at = NEW.deleted_at where id = r.id;
      insert into public.achievement_xp_log (worker_name, achievement_id, xp_earned, source_action, source_id, reversed_at)
      values (r.worker_name, r.achievement_id, -r.xp_earned, r.source_action, NEW.id::text, NEW.deleted_at);
    end loop;
  else
    -- Only what THIS delete took back, read from the NEGATIVE rows it wrote (stamped with its own deleted_at, a
    -- clock instant), so a second delete-and-restore cannot hand the same XP back twice. Not from the original
    -- positive rows: the weekly achievement-xp-log-purge deletes rows by earned_at, and an entry earned 80 days
    -- ago would lose its originals a few days into its stay in Recently deleted - a restore would then give back
    -- nothing. The negative rows are written at delete time, and the purge below keeps them while the entry waits.
    for r in
      select worker_name, achievement_id, -xp_earned as xp, source_action
        from public.achievement_xp_log
       where source_id = NEW.id::text and xp_earned < 0 and reversed_at = OLD.deleted_at
    loop
      perform public.award_achievement_xp(r.worker_name, r.achievement_id, r.xp, r.source_action, NEW.id::text);
    end loop;
  end if;
  return NEW;
end;
$$;

drop trigger if exists trg_logbook_xp_on_trash on public.logbook;
create trigger trg_logbook_xp_on_trash after update of deleted_at on public.logbook
  for each row execute function public.trg_logbook_xp_on_trash();

-- ── 7. A name a deleted row still holds ──────────────────────────────────────────────────────────────────────
-- Asset tag and part number: say where it is rather than a bare "duplicate key".
create or replace function public.guard_name_held_by_deleted()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if TG_TABLE_NAME = 'asset_nodes' then
    if NEW.tag is not null and exists (
         select 1 from public.asset_nodes a
          where a.hive_id = NEW.hive_id and a.tag = NEW.tag and a.deleted_at is not null
            and a.id is distinct from NEW.id) then
      raise exception 'Tag % belongs to an asset in Recently deleted. Restore it there, or use another tag.', NEW.tag
        using errcode = '23505';
    end if;
  elsif TG_TABLE_NAME = 'inventory_items' then
    if NEW.part_number is not null and exists (
         select 1 from public.inventory_items i
          where i.hive_id = NEW.hive_id and i.part_number = NEW.part_number and i.deleted_at is not null
            and i.id is distinct from NEW.id) then
      raise exception 'Part number % belongs to a part in Recently deleted. Restore it there, or use another part number.', NEW.part_number
        using errcode = '23505';
    end if;
  end if;
  return NEW;
end;
$$;

drop trigger if exists trg_name_held_by_deleted on public.asset_nodes;
create trigger trg_name_held_by_deleted before insert on public.asset_nodes
  for each row execute function public.guard_name_held_by_deleted();
drop trigger if exists trg_name_held_by_deleted on public.inventory_items;
create trigger trg_name_held_by_deleted before insert on public.inventory_items
  for each row execute function public.guard_name_held_by_deleted();

-- A project link or role has nothing under it: re-adding it replaces the deleted copy.
create or replace function public.replace_deleted_pairing()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if TG_TABLE_NAME = 'project_links' then
    if NEW.link_id is not null then
      delete from public.project_links k
       where k.project_id = NEW.project_id and k.link_type = NEW.link_type and k.link_id = NEW.link_id
         and k.deleted_at is not null;
    end if;
  elsif TG_TABLE_NAME = 'project_roles' then
    delete from public.project_roles r
     where r.project_id = NEW.project_id and r.worker_name = NEW.worker_name and r.role = NEW.role
       and r.deleted_at is not null;
  end if;
  return NEW;
end;
$$;

drop trigger if exists trg_replace_deleted_pairing on public.project_links;
create trigger trg_replace_deleted_pairing before insert on public.project_links
  for each row execute function public.replace_deleted_pairing();
drop trigger if exists trg_replace_deleted_pairing on public.project_roles;
create trigger trg_replace_deleted_pairing before insert on public.project_roles
  for each row execute function public.replace_deleted_pairing();

-- ── 8. The purge after the retention window ─────────────────────────────────────────────────────────────────
create or replace function public.hard_delete_expired_soft_deletes()
returns integer
language plpgsql
security definer
set search_path = public
as $$
DECLARE
  v_hive      record;
  v_total     integer := 0;
  v_retention integer;
  v_n         integer;
  v_t         text;
BEGIN
  FOR v_hive IN
    SELECT h.id, COALESCE(hrc.soft_delete_retention_days, 30) AS keep_days
      FROM public.hives h
      LEFT JOIN public.hive_retention_config hrc ON hrc.hive_id = h.id
  LOOP
    v_retention := v_hive.keep_days;

    DELETE FROM public.community_posts
      WHERE hive_id = v_hive.id
        AND deleted_at IS NOT NULL
        AND deleted_at < now() - make_interval(days => v_retention);
    GET DIAGNOSTICS v_n = ROW_COUNT;
    v_total := v_total + v_n;   -- accumulate across hives

    -- D3 (2026-10-16): the pages' recoverable deletes. Pairings first, then rows that others point at.
    FOREACH v_t IN ARRAY ARRAY['project_roles','project_links','logbook','inventory_items','pm_assets','asset_nodes']
    LOOP
      EXECUTE format('DELETE FROM public.%I WHERE hive_id = $1 AND deleted_at IS NOT NULL '
                     'AND deleted_at < now() - make_interval(days => $2)', v_t)
        USING v_hive.id, v_retention;
      GET DIAGNOSTICS v_n = ROW_COUNT;
      v_total := v_total + v_n;
    END LOOP;
  END LOOP;

  -- Personal rows (no hive): a day plan, a solo logbook, solo assets and parts - the default 30 days.
  FOREACH v_t IN ARRAY ARRAY['schedule_items','logbook','inventory_items','pm_assets','asset_nodes']
  LOOP
    EXECUTE format('DELETE FROM public.%I WHERE %s deleted_at IS NOT NULL '
                   'AND deleted_at < now() - interval ''30 days''',
                   v_t, CASE WHEN v_t = 'schedule_items' THEN '' ELSE 'hive_id IS NULL AND' END);
    GET DIAGNOSTICS v_n = ROW_COUNT;
    v_total := v_total + v_n;
  END LOOP;

  -- Telemetry retention is hive-agnostic; one pass over the whole ledger.
  DELETE FROM public.ai_cost_log
    WHERE created_at < now() - interval '365 days';

  RETURN v_total;
END;
$$;

-- ── 9. The asset and PM-asset delete audits now fire at the purge: name it, and name who did it ────────────

CREATE OR REPLACE FUNCTION public.audit_asset_node_delete()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor      text;
  v_fmea       integer;
  v_strategies integer;
  v_weibull    integer;
  v_pf         integer;
  v_readings   integer;
  v_logbook    integer;
BEGIN
  -- SOLO lane (2026-09-02): hive_audit_log.hive_id is NOT NULL and its audience is the hive.
  -- A hive-less node has neither — auditing would abort the delete itself.
  IF OLD.hive_id IS NULL THEN
    RETURN OLD;
  END IF;

  -- BEFORE DELETE: the cascade has not run, so the children are still countable. After the
  -- statement completes none of this can be reconstructed.
  SELECT count(*) INTO v_fmea       FROM public.rcm_fmea_modes WHERE asset_id = OLD.id;
  SELECT count(*) INTO v_strategies FROM public.rcm_strategies s
    JOIN public.rcm_fmea_modes f ON f.id = s.fmea_mode_id WHERE f.asset_id = OLD.id;
  SELECT count(*) INTO v_weibull    FROM public.weibull_fits  WHERE asset_id = OLD.id;
  SELECT count(*) INTO v_pf         FROM public.pf_intervals  WHERE asset_id = OLD.id;
  SELECT count(*) INTO v_readings   FROM public.sensor_readings WHERE asset_id = OLD.id;
  -- SET NULL rather than CASCADE — these SURVIVE, but they lose their link to the asset, so the
  -- count is worth recording as "orphaned", not "destroyed".
  SELECT count(*) INTO v_logbook    FROM public.logbook WHERE asset_node_id = OLD.id;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND hm.hive_id = OLD.hive_id
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    OLD.hive_id,
    CASE WHEN OLD.deleted_at IS NOT NULL AND auth.uid() IS NULL THEN 'retention purge'
         ELSE COALESCE(v_actor, OLD.worker_name, 'unknown') END,
    -- D3: a row deleted earlier and removed now by the retention job is a purge, not a new delete
    CASE WHEN OLD.deleted_at IS NOT NULL THEN 'purge_asset_node' ELSE 'delete_asset_node' END,
    'asset_nodes',
    OLD.id::text,
    COALESCE(OLD.tag, OLD.name, '(unnamed asset)'),
    jsonb_build_object(
      'status_was',            OLD.status,
      'criticality',           OLD.criticality,
      'fmea_modes_destroyed',  v_fmea,
      'rcm_strategies_destroyed', v_strategies,
      'weibull_fits_destroyed',   v_weibull,
      'pf_intervals_destroyed',   v_pf,
      -- The evidence base. Without these no future fit for this machine is derivable.
      'sensor_readings_destroyed', v_readings,
      'logbook_entries_orphaned',  v_logbook,
      'source',                'db_trigger'
    )
  );

  RETURN OLD;
END;
$function$;

CREATE OR REPLACE FUNCTION public.audit_pm_asset_delete()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor  text;
  v_comps  integer;
  v_scope  integer;
  v_oldest timestamptz;
BEGIN
  -- SOLO lane (2026-09-02): hive_audit_log.hive_id is NOT NULL and its audience is the hive.
  IF OLD.hive_id IS NULL THEN
    RETURN OLD;
  END IF;

  -- BEFORE DELETE: the cascade has not run yet, so the children are still countable. After the
  -- statement completes this information no longer exists anywhere.
  SELECT count(*), min(completed_at) INTO v_comps, v_oldest
    FROM public.pm_completions WHERE asset_id = OLD.id;
  SELECT count(*) INTO v_scope
    FROM public.pm_scope_items WHERE asset_id = OLD.id;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND hm.hive_id = OLD.hive_id
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    OLD.hive_id,
    CASE WHEN OLD.deleted_at IS NOT NULL AND auth.uid() IS NULL THEN 'retention purge'
         ELSE COALESCE(v_actor, OLD.worker_name, 'unknown') END,
    -- D3: a row deleted earlier and removed now by the retention job is a purge, not a new delete
    CASE WHEN OLD.deleted_at IS NOT NULL THEN 'purge_pm_asset' ELSE 'delete_pm_asset' END,
    'pm_assets',
    OLD.id::text,
    COALESCE(OLD.asset_name, '(unnamed asset)'),
    jsonb_build_object(
      'criticality',            OLD.criticality,
      'category',               OLD.category,
      -- What the deletion actually cost, which is the part nobody could see.
      'completions_destroyed',  v_comps,
      'scope_items_destroyed',  v_scope,
      'history_began',          v_oldest,
      'source',                 'db_trigger'
    )
  );

  RETURN OLD;
END;
$function$;

-- ── 10. Deleting a closed entry is not an amendment of it ─────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.audit_logbook_post_close_amendment()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
BEGIN
  -- SOLO lane (2026-09-02, VM7 walk): hive_audit_log.hive_id is NOT NULL and its audience
  -- is the hive. A hive-less row has neither; without this early return the audit INSERT
  -- ABORTS the user's own edit (proven live per-fn in rolled-back probes).
  IF NEW.hive_id IS NULL THEN
    RETURN NEW;
  END IF;

  -- Only rows that were already signed off. Everything else is an ordinary edit.
  IF COALESCE(OLD.status, '') <> 'Closed' THEN
    RETURN NEW;
  END IF;

  -- Ignore no-op updates (a re-save that changed nothing is not an amendment).
  IF NEW IS NOT DISTINCT FROM OLD THEN
    RETURN NEW;
  END IF;

  -- ★ADOPTION IS NOT AN AMENDMENT (2026-10-08, 20261008000064). A closed entry its owner brings from their personal
  -- history into a hive (bring_personal_history_into_hive) changes ONLY hive_id - plus the updated_at the touch trigger
  -- stamps. Its words, sign-off and dates are exactly what they were, so "amended after close" would tell a supervisor
  -- something untrue; the adoption is recorded once, by the function that made it, under the person's own name.
  IF OLD.hive_id IS NULL AND NEW.hive_id IS NOT NULL
     AND (to_jsonb(NEW) - 'hive_id' - 'updated_at') = (to_jsonb(OLD) - 'hive_id' - 'updated_at') THEN
    RETURN NEW;
  END IF;

  -- D3 (2026-10-16): deleting or restoring a closed entry is not an amendment - its words and sign-off are
  -- untouched. trg_audit_trash_transition records it as delete / recover.
  IF (to_jsonb(NEW) - 'deleted_at' - 'deleted_by' - 'updated_at') = (to_jsonb(OLD) - 'deleted_at' - 'deleted_by' - 'updated_at') THEN
    RETURN NEW;
  END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND (NEW.hive_id IS NULL OR hm.hive_id = NEW.hive_id)
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    NEW.hive_id,
    COALESCE(v_actor, NEW.worker_name, 'unknown'),
    CASE WHEN COALESCE(NEW.status, '') <> 'Closed'
         THEN 'reopen_closed_logbook_entry'
         ELSE 'amend_closed_logbook_entry' END,
    'logbook',
    NEW.id,
    COALESCE(NEW.machine, '(no machine)'),
    jsonb_build_object(
      'prev_status',    OLD.status,
      'new_status',     NEW.status,
      'closed_at_was',  OLD.closed_at,
      'closed_at_now',  NEW.closed_at,
      'source',         'db_trigger'
    )
  );

  RETURN NEW;
END;
$function$;

-- ── 11. A deleted logbook entry stops answering the AI ───────────────────────────────────────────────────────
-- fault_knowledge is derived from logbook entries (embed relay, upsert on logbook_id) and read by the AI's
-- searches, often under the service role, which no policy hides from. It is derived and rebuildable, so a
-- delete removes it outright and a restore re-queues the entry for embedding.
CREATE OR REPLACE FUNCTION public.enqueue_for_embedding()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  j       jsonb;
  v_hive  uuid;
  v_auth  uuid;
  v_id    text;
BEGIN
  -- An inactive or unregistered surface enqueues nothing, so a trigger can be attached ahead of the config
  -- and switched on by flipping `active` — no DDL to enable a surface.
  IF NOT EXISTS (SELECT 1 FROM public.embedding_registry r
                  WHERE r.source_table = TG_TABLE_NAME AND r.active) THEN
    RETURN NULL;
  END IF;

  j    := to_jsonb(NEW);
  -- D3 (2026-10-16): a deleted row is not indexed. Its knowledge is removed when it is deleted
  -- (trg_logbook_knowledge_on_trash) and rebuilt when it is restored - the restore is an UPDATE that
  -- re-enters here with deleted_at cleared.
  IF nullif(j->>'deleted_at', '') IS NOT NULL THEN
    RETURN NULL;
  END IF;
  v_id := j->>'id';
  IF v_id IS NULL THEN
    RETURN NULL;                       -- nothing addressable to re-read later
  END IF;

  -- These columns are absent on some surfaces; a missing key yields NULL rather than an error, which is why
  -- the cast is guarded instead of assumed.
  BEGIN v_hive := nullif(j->>'hive_id','')::uuid;  EXCEPTION WHEN others THEN v_hive := NULL; END;
  BEGIN v_auth := nullif(j->>'auth_uid','')::uuid; EXCEPTION WHEN others THEN v_auth := NULL; END;

  INSERT INTO public.embedding_outbox (source_table, row_id, hive_id, auth_uid, op)
  VALUES (TG_TABLE_NAME, v_id, v_hive, v_auth, TG_OP)
  ON CONFLICT (source_table, row_id) WHERE done_at IS NULL
  DO UPDATE SET enqueued_at     = now(),
                op              = EXCLUDED.op,
                attempts        = 0,
                next_attempt_at = now(),
                last_error      = NULL;
  RETURN NULL;                          -- AFTER trigger: the return value is ignored
END
$function$;

create or replace function public.trg_logbook_knowledge_on_trash()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if OLD.deleted_at is null and NEW.deleted_at is not null then
    delete from public.fault_knowledge where logbook_id = NEW.id::text;
  end if;
  return NEW;
end;
$$;

drop trigger if exists trg_logbook_knowledge_on_trash on public.logbook;
create trigger trg_logbook_knowledge_on_trash after update of deleted_at on public.logbook
  for each row execute function public.trg_logbook_knowledge_on_trash();

-- ── 12. The 30-second post limit keeps counting a deleted post ───────────────────────────────────────────────
-- community_post_rate_limit ran as the poster, so once deleted posts are hidden from the poster it would stop
-- counting them - and deleting a post would buy another one inside the window. It only counts, so it runs as the
-- owner now (the logbook's own limit, check_logbook_rate_limit, already does).
alter function public.community_post_rate_limit() security definer;
alter function public.community_post_rate_limit() set search_path = public;

-- ── 13. The weekly XP-log purge keeps what a restore will need ───────────────────────────────────────────────
-- achievement-xp-log-purge (20260508000002) deletes log rows older than 90 days. A restore gives back the XP a
-- delete took by reading the delete's own reversal rows (section 6), so those are kept for as long as their entry
-- is still in Recently deleted - a hive may keep deleted items longer than 90 days. Same name, so this replaces it.
select cron.schedule(
  'achievement-xp-log-purge',
  '0 3 * * 0',
  $$DELETE FROM public.achievement_xp_log x
     WHERE x.earned_at < now() - interval '90 days'
       AND NOT (x.xp_earned < 0 AND x.reversed_at IS NOT NULL
                AND EXISTS (SELECT 1 FROM public.logbook l
                             WHERE l.id = x.source_id AND l.deleted_at = x.reversed_at))$$
);
