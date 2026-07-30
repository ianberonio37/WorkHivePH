-- TB-FWD-forward-only-status.sql
--
-- Two forward-only status machines, both found unscored 2026-07-31 (ARC 13 / F):
--   anomaly_signals_forward_only_status  — 'resolved'/'expired' are terminal; a row cannot regress out of them.
--   shift_plans_forward_only_status      — draft(0) -> published(1) -> archived(2); rank cannot go backward.
--
-- Neither guard checks auth.uid(): the ratchet applies to EVERY caller, including the backend, so no jwt is
-- needed and no other trigger's verdict is involved. Fixtures are planted at a known status, then a regress and
-- a legitimate forward move are each attempted. Every refusal is paired with the forward move it must still
-- allow, so 'forward-only' is separated from 'frozen'.
begin;

-- ── anomaly_signals: cannot regress out of a terminal state ──
insert into public.anomaly_signals(id, hive_id, machine, status)
  values ('e1000000-0000-4000-8000-0000000000a1','b4f7fe63-92e1-4f8d-b96e-625c3f85ba61','TB-MACHINE','resolved');
do $p$
declare n int;
begin
  begin update public.anomaly_signals set status='active' where id='e1000000-0000-4000-8000-0000000000a1';
        get diagnostics n=row_count; raise notice 'RESULT anom_regress=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT anom_regress=blocked'; end;
  -- terminal -> terminal (resolved -> expired) is NOT a regress, so it is allowed
  begin update public.anomaly_signals set status='expired' where id='e1000000-0000-4000-8000-0000000000a1';
        get diagnostics n=row_count; raise notice 'RESULT anom_terminal_to_terminal=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT anom_terminal_to_terminal=BLOCKED'; end;
end $p$;
-- forward move from a non-terminal state is allowed
insert into public.anomaly_signals(id, hive_id, machine, status)
  values ('e1000000-0000-4000-8000-0000000000a2','b4f7fe63-92e1-4f8d-b96e-625c3f85ba61','TB-MACHINE-2','active');
do $p$
declare n int;
begin
  begin update public.anomaly_signals set status='resolved' where id='e1000000-0000-4000-8000-0000000000a2';
        get diagnostics n=row_count; raise notice 'RESULT anom_forward=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT anom_forward=BLOCKED'; end;
end $p$;

-- ── shift_plans: rank cannot go backward ──
insert into public.shift_plans(id, hive_id, shift_window, status)
  values ('e2000000-0000-4000-8000-0000000000b1','b4f7fe63-92e1-4f8d-b96e-625c3f85ba61','06-14','published');
do $p$
declare n int;
begin
  begin update public.shift_plans set status='draft' where id='e2000000-0000-4000-8000-0000000000b1';
        get diagnostics n=row_count; raise notice 'RESULT shift_regress=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT shift_regress=blocked'; end;
  begin update public.shift_plans set status='archived' where id='e2000000-0000-4000-8000-0000000000b1';
        get diagnostics n=row_count; raise notice 'RESULT shift_forward=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT shift_forward=BLOCKED'; end;
end $p$;

rollback;
