-- SL LB1 (2026-10-21): what a resume says about a worker's logbook is the WHOLE logbook, not its newest 300 rows.
--
-- resume.html's "Fill from my WorkHive data" read the worker's newest 300 logbook entries and wrote, into the resume a
-- person hands to an employer: "Logged {rows} maintenance records across {distinct machines} equipment items", "{rows}
-- documented maintenance jobs", and a start year taken from the oldest of those 300. Measured on the local data: the
-- busiest worker holds 3,666 entries - the resume said 300, named a fraction of the equipment, and dated their
-- experience from the start of the newest slice. A cap shown as a total, on the one document whose whole point is the
-- person's history.
--
-- The three figures are a COUNT, a DISTINCT COUNT and a MIN - none of which a capped read can give. This function returns
-- them from the database, as the caller (SECURITY INVOKER over v_logbook_truth, which is itself security_invoker, so the
-- logbook's own RLS decides every row exactly as the page's read did). It scopes by the ACCOUNT, and reaches a name only
-- for rows no account holds (the rule SL AU3 set for "my records": a namesake's rows are never the caller's).
-- The page keeps its newest-300 read for the HIGHLIGHTS (the eight biggest downtime jobs it lists), and the summary
-- sentences use these figures.

create or replace function public.my_logbook_summary(p_worker_name text default null)
returns table (entries bigint, equipment bigint, first_date date)
language sql
stable
security invoker
set search_path = public
as $$
  select count(*)::bigint,
         count(distinct nullif(trim(coalesce(nullif(trim(l.asset_tag), ''), l.machine)), ''))::bigint,
         (min(coalesce(l.date, l.created_at)) at time zone 'Asia/Manila')::date
  from public.v_logbook_truth l
  where (auth.uid() is not null and l.auth_uid = auth.uid())
     or (l.auth_uid is null and p_worker_name is not null and l.worker_name = p_worker_name);
$$;

comment on function public.my_logbook_summary(text) is
  'SL LB1: the caller''s whole logbook as three figures (entries, distinct equipment, first date) - the resume''s summary '
  'sentences, which a capped read can never give. Invoker: RLS decides every row. By account; a name reaches only '
  'rows no account holds.';

revoke all on function public.my_logbook_summary(text) from public, anon;   -- BRH-Y: Supabase grants anon EXECUTE explicitly, so "from public" alone never reached it
grant execute on function public.my_logbook_summary(text) to authenticated;

-- The logbook's "⇄ SAP PM" badge says which machines arrive from a CMMS. It was drawn from any 500 synced work orders -
-- one row per WORK ORDER - so one busy machine's history could fill the read and every other synced machine lost its
-- badge, with nothing said. The badge needs one row per MACHINE: its newest sync source. A set the plant bounds, not
-- a stream. Invoker over v_external_sync_truth (security_invoker): the caller's RLS decides every row.
create or replace function public.logbook_synced_machines(p_hive_id uuid)
returns table (machine text, system_type text)
language sql
stable
security invoker
set search_path = public
as $$
  select distinct on (s.sync_payload->>'machine') s.sync_payload->>'machine', s.system_type
  from public.v_external_sync_truth s
  where s.hive_id = p_hive_id and s.entity_type = 'work_order' and coalesce(s.sync_payload->>'machine', '') <> ''
  order by s.sync_payload->>'machine', s.last_synced_at desc nulls last, s.id;
$$;

comment on function public.logbook_synced_machines(uuid) is
  'SL LB1: one row per machine a CMMS syncs work orders for, with its newest source - the logbook badge, which a '
  '500-work-order read could not give. Invoker: RLS decides every row.';

revoke all on function public.logbook_synced_machines(uuid) from public, anon;   -- BRH-Y: the same
grant execute on function public.logbook_synced_machines(uuid) to authenticated;
