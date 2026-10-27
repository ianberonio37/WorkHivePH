-- TB-APPROVAL-supervisor-only.sql
--
-- `wh_guard_supervisor_approval` gates the REVIEWER-only fields on three tables (rcm_fmea_modes,
-- project_change_orders, project_progress_logs): a change that approves/assigns/verifies (touches approved_at/
-- approved_by, a status of approved/rejected, wo_state of approved/assigned/verified, or a rejection reason) is
-- refused unless the caller is a SUPERVISOR of the row's hive. A non-privileged change is anyone's. Found
-- unscored 2026-07-31 (ARC 13 / F). Scored on project_change_orders.
--
-- Guard-isolated: change orders are planted as postgres (auth.uid() null -> the guard's backend branch), then
-- each identity's jwt claims are set. A status change to 'approved' is the privileged act; a change to
-- 'cancelled' is not (neither the old nor the new status is a reviewer state), and it does not touch the pinned
-- terms, so guard_change_order_terms_immutable also allows it. Real Baguio worker + supervisor.
begin;

-- ★WHO ACTS IS RESOLVED BY WHAT THEY ARE, NOT BY A LITERAL ID (2026-10-28). This probe named its worker, supervisor,
-- outsider and project by literal uuids; the clean reseed (2026-10-27) recreated every account and project, so each id
-- named nobody - the supervisor's legitimate writes read BLOCKED, the change orders broke their foreign key, and the
-- same literal was flagged on push as a leaked "secret". A missing one stops the probe loudly: a null sub would read
-- as the backend's allow-branch and the probe would test nothing.
create temp table _tb as select
  (select id from auth.users where email = 'bryangarcia@auth.workhiveph.com') as worker,
  (select m.auth_uid from public.hive_members m where m.hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' and m.role = 'supervisor'
      and m.status = 'active' and m.auth_uid is not null
      and m.auth_uid not in (select auth_uid from public.marketplace_platform_admins where auth_uid is not null)
    order by m.worker_name limit 1) as supervisor,
  (select m.auth_uid from public.hive_members m where m.hive_id = 'b4f7fe63-92e1-4f8d-b96e-625c3f85ba61' and m.role = 'worker'
      and m.status = 'active' and m.auth_uid is not null
      and m.auth_uid not in (select auth_uid from public.hive_members where hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' and auth_uid is not null)
    order by m.worker_name limit 1) as outsider,
  (select p.id from public.projects p where p.hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' and p.deleted_at is null
    order by p.created_at, p.id limit 1) as project;
do $tb$ begin
  if exists (select 1 from _tb where project is null or supervisor is null or worker is null) then
    raise exception 'probe fixture missing: %', (select row_to_json(_tb)::text from _tb);
  end if;
end $tb$;


insert into public.project_change_orders(id, project_id, hive_id, co_number, title, scope_change, requested_by, status) values
  ('a7000000-0000-4000-8000-00000000a501'::uuid,(select project from _tb),
   '084c113b-99c0-45c6-a8e8-b4b8349da46d','CO-AP-1','TB CO','scope','TB Req','pending'),
  ('a7000000-0000-4000-8000-00000000a502'::uuid,(select project from _tb),
   '084c113b-99c0-45c6-a8e8-b4b8349da46d','CO-AP-2','TB CO 2','scope','TB Req','pending');

-- a WORKER cannot APPROVE (a privileged change)
select set_config('request.jwt.claims',json_build_object('sub', (select worker from _tb), 'role', 'authenticated')::text, true);
do $p$
declare n int;
begin
  begin update public.project_change_orders set status='approved' where id='a7000000-0000-4000-8000-00000000a501';
        get diagnostics n=row_count; raise notice 'RESULT worker_approves=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT worker_approves=blocked'; end;
  -- but a NON-privileged change (cancel, from pending) is allowed
  begin update public.project_change_orders set status='cancelled' where id='a7000000-0000-4000-8000-00000000a502';
        get diagnostics n=row_count; raise notice 'RESULT worker_nonpriv=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT worker_nonpriv=BLOCKED'; end;
end $p$;

-- a SUPERVISOR of the hive can approve
select set_config('request.jwt.claims',json_build_object('sub', (select supervisor from _tb), 'role', 'authenticated')::text, true);
do $p$
declare n int;
begin
  begin update public.project_change_orders set status='approved' where id='a7000000-0000-4000-8000-00000000a501';
        get diagnostics n=row_count; raise notice 'RESULT sup_approves=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT sup_approves=BLOCKED sqlstate=%', sqlstate; end;
end $p$;

rollback;
