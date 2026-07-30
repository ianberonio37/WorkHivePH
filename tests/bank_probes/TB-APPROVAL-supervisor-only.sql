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

insert into public.project_change_orders(id, project_id, hive_id, co_number, title, scope_change, requested_by, status) values
  ('a7000000-0000-4000-8000-00000000a501'::uuid,'539e0d9a-9ff7-474b-ab03-9254406ca7dc',
   '084c113b-99c0-45c6-a8e8-b4b8349da46d','CO-AP-1','TB CO','scope','TB Req','pending'),
  ('a7000000-0000-4000-8000-00000000a502'::uuid,'539e0d9a-9ff7-474b-ab03-9254406ca7dc',
   '084c113b-99c0-45c6-a8e8-b4b8349da46d','CO-AP-2','TB CO 2','scope','TB Req','pending');

-- a WORKER cannot APPROVE (a privileged change)
select set_config('request.jwt.claims','{"sub":"91e0d1eb-cd96-43ee-af5f-0ff2714b3923","role":"authenticated"}', true);
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
select set_config('request.jwt.claims','{"sub":"bcb5a6e3-fb12-4238-bc1e-ffeb48f60d53","role":"authenticated"}', true);
do $p$
declare n int;
begin
  begin update public.project_change_orders set status='approved' where id='a7000000-0000-4000-8000-00000000a501';
        get diagnostics n=row_count; raise notice 'RESULT sup_approves=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT sup_approves=BLOCKED sqlstate=%', sqlstate; end;
end $p$;

rollback;
