-- Three of seven providers were invisible to every broadcast, and none of them were working.
--
-- `service_providers.availability` is written in exactly one place — sync_provider_availability, a
-- trigger on service_requests. It sets 'on_job' when a job enters accepted/en_route/on_site/in_progress,
-- and back to 'online' on settled/cancelled_by_client/cancelled_by_provider/expired.
--
-- Two holes, and the live data shows both:
--
-- 1. `completed` is in NEITHER list. A provider who has finished the work stays 'on_job' until the CLIENT
--    presses Release. Under confirm-to-release the client has already received the service and has
--    already paid the provider directly — outside the platform — so the only thing Release still does for
--    them is mint their own 1% cashback. A provider's ability to earn should not hang on that. Availability
--    answers "can this person take new work?", not "is the paperwork closed?", and someone who has
--    completed the job can plainly take new work.
--
-- 2. The release only ever happens ON a transition. If the transition never comes, or the request row is
--    removed, or a seed writes 'on_job' with no job behind it, the provider is stranded PERMANENTLY —
--    there is no reconciler and no timeout. sweep_service_broadcasts only touches status='broadcasting'.
--    Measured on this database before the fix: FOUR providers marked 'on_job', and not one of them had a
--    request in any active state. Three predate this session. That is 43% of supply silently withdrawn
--    from the market, and no gate, dashboard or test could see it — the same shape as the config change
--    that once froze 71% of supply, arrived at from the opposite direction.
--
-- The fix is both halves: release on completed, AND reconcile the drift every minute so the invariant
-- (on_job ⇒ there is an active job) becomes self-healing rather than write-once-and-hope.

-- ---------------------------------------------------------------------------------------------------
-- 1 · completed releases the provider
-- ---------------------------------------------------------------------------------------------------
create or replace function public.sync_provider_availability()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
begin
  if new.matched_provider_id is null then return new; end if;
  if new.status in ('accepted','en_route','on_site','in_progress') then
    update public.service_providers set availability = 'on_job', updated_at = now()
    where id = new.matched_provider_id and availability <> 'on_job';
  elsif new.status in ('completed','settled','cancelled_by_client','cancelled_by_provider','expired',
                       'disputed') then
    -- 'completed' added: the work is done, so the provider is available even though the money has not
    -- been released yet. 'disputed' added for the same reason — a job under dispute is not a job being
    -- worked, and freezing the provider's earnings is not a dispute remedy, it is a second penalty.
    update public.service_providers set availability = 'online', updated_at = now()
    where id = new.matched_provider_id and availability = 'on_job';
  end if;
  return new;
end $function$;

-- ---------------------------------------------------------------------------------------------------
-- 2 · the invariant becomes self-healing
-- ---------------------------------------------------------------------------------------------------
create or replace function public.reconcile_provider_availability()
returns integer
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_freed integer;
begin
  -- on_job is only true while an actual job is in an active state. Anything else is drift, and drift
  -- here means a provider who cannot be found and does not know why.
  update public.service_providers sp
     set availability = 'online', updated_at = now()
   where sp.availability = 'on_job'
     and not exists (
       select 1 from public.service_requests r
        where r.matched_provider_id = sp.id
          and r.status in ('accepted','en_route','on_site','in_progress')
     );
  get diagnostics v_freed = row_count;
  return v_freed;
end $function$;

revoke all on function public.reconcile_provider_availability() from public, anon, authenticated;

comment on function public.reconcile_provider_availability() is
  'Frees providers marked on_job with no active job. availability was write-once via a transition '
  'trigger, so any missed transition stranded a provider permanently — measured at 4 of 7 providers, '
  'none of them working. Runs every minute beside sweep_service_broadcasts.';

-- Ride the existing 1-minute service sweep rather than adding another schedule.
select cron.schedule(
  'service-availability-reconcile-1min',
  '* * * * *',
  $$SELECT public.reconcile_provider_availability();$$
);

-- Heal what is already stranded.
select public.reconcile_provider_availability();
