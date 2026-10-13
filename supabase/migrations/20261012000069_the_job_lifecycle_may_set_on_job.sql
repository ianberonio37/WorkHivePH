-- THE JOB LIFECYCLE MAY SET on_job (2026-10-12, UFAI W4464, walked as a provider on marketplace-seller.html).
--
-- guard_service_provider_writes refuses availability = 'on_job' unless the write is the system's: no auth.uid(), a
-- marketplace admin, or a session flagged workhive.service_system_write = 'on'. Every lifecycle function that moves a
-- provider sets that flag first (accept_service_request, select_quote, apply_credits_to_request, ...). The one that
-- did not is sync_provider_availability - the AFTER UPDATE OF status trigger that keeps a provider's availability in
-- step with their job - and it runs inside the PROVIDER's own session. Accept had normally set on_job already, so its
-- update matched nothing; but a provider who went back to 'online' mid-job (the toggle is theirs to press) and then
-- advanced the job (en route, on site, in progress) was refused with the raw sentence "Not allowed: on_job is set by
-- the job lifecycle" - by the job lifecycle itself - and the job could not move.
--
-- The trigger now flags its own write, and restores the flag to what it was right after, so the AFTER triggers that
-- follow it in the same statement inherit nothing.

create or replace function public.sync_provider_availability()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'pg_catalog', 'public'
as $function$
declare
  _prev text := current_setting('workhive.service_system_write', true);
begin
  if new.matched_provider_id is null then return new; end if;
  perform set_config('workhive.service_system_write', 'on', true);
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
  perform set_config('workhive.service_system_write', coalesce(_prev, ''), true);
  return new;
end $function$;

notify pgrst, 'reload schema';
