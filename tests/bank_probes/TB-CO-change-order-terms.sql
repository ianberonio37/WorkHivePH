-- TB-CO-change-order-terms.sql
--
-- `guard_change_order_terms_immutable` makes the COMMERCIAL TERMS of a raised change order fixed. A change
-- order is a contract amendment, so once it is raised its cost, schedule, scope, title, requester, project and
-- hive may not be quietly rewritten — the amendment trail has to mean something. The lifecycle fields (status,
-- approver, rejection reason) are deliberately NOT pinned here; wh_guard_supervisor_approval owns WHO may move
-- it through its states. A DELETE is refused outright: cancel it instead, so it stays on record.
--
-- Found unscored 2026-07-31 (ARC 13 / F). Unlike the trust guards this one shares no variable names with the
-- service_request status machines and calls neither is_marketplace_admin() nor a system-write GUC, so no generic
-- operator bleeds onto it — it scores against its own five operators alone.
--
-- Guard-isolated: the CO is planted as postgres (auth.uid() null -> the guard's own backend branch, which also
-- lets the fixture exist), and the term edits are attempted with a real user's jwt claims (RLS bypassed). A
-- term change is refused ONLY by this trigger, so what blocks it is unambiguous. The legitimate write is the
-- BACKEND edit (auth.uid() null), which is this guard's own allow-branch, so the positive isolates the guard
-- rather than depending on another trigger's verdict.
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
  if exists (select 1 from _tb where outsider is null or project is null) then
    raise exception 'probe fixture missing: %', (select row_to_json(_tb)::text from _tb);
  end if;
end $tb$;


insert into public.project_change_orders(id, project_id, hive_id, co_number, title, scope_change, requested_by,
       status, cost_impact_php, schedule_impact_days)
  values ('cf000000-0000-4000-8000-0000000000c1',(select project from _tb),
          '084c113b-99c0-45c6-a8e8-b4b8349da46d','CO-TB-1','TB original title','TB original scope',
          'TB Requester','pending', 1000, 5);

-- POSITIVE: the backend branch (auth.uid() null) may still adjust terms — a seeder/service write. This is the
-- guard's own allow-path, so no other trigger's opinion is involved.
do $probe$
declare n int;
begin
  begin update public.project_change_orders set cost_impact_php=1200 where id='cf000000-0000-4000-8000-0000000000c1';
        get diagnostics n=row_count; raise notice 'RESULT backend_edit=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT backend_edit=BLOCKED sqlstate=%', sqlstate; end;
end $probe$;

-- ── A USER MAY NOT REWRITE THE RAISED TERMS ──
select set_config('request.jwt.claims',
  json_build_object('sub', (select outsider from _tb), 'role', 'authenticated')::text, true);
do $probe$
declare n int;
begin
  begin update public.project_change_orders set cost_impact_php=5 where id='cf000000-0000-4000-8000-0000000000c1';
        get diagnostics n=row_count; raise notice 'RESULT user_edits_cost=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT user_edits_cost=blocked'; end;

  begin update public.project_change_orders set title='TB hijacked title' where id='cf000000-0000-4000-8000-0000000000c1';
        get diagnostics n=row_count; raise notice 'RESULT user_edits_title=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT user_edits_title=blocked'; end;

  begin update public.project_change_orders set scope_change='TB hijacked scope' where id='cf000000-0000-4000-8000-0000000000c1';
        get diagnostics n=row_count; raise notice 'RESULT user_edits_scope=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT user_edits_scope=blocked'; end;

  begin update public.project_change_orders set co_number='CO-TB-HIJACK' where id='cf000000-0000-4000-8000-0000000000c1';
        get diagnostics n=row_count; raise notice 'RESULT user_edits_conumber=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT user_edits_conumber=blocked'; end;

  begin update public.project_change_orders set schedule_impact_days=99 where id='cf000000-0000-4000-8000-0000000000c1';
        get diagnostics n=row_count; raise notice 'RESULT user_edits_schedule=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT user_edits_schedule=blocked'; end;

  -- and it may not be DELETED (cancel instead)
  begin delete from public.project_change_orders where id='cf000000-0000-4000-8000-0000000000c1';
        get diagnostics n=row_count; raise notice 'RESULT user_deletes=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT user_deletes=blocked'; end;
end $probe$;

rollback;
