-- BRH-AQ, the domain slice (2026-11-11): a state change is timed by the server, not by the member.
--
-- 20261111000001 pinned created_at. Fifteen more time columns a signed-in member could rewrite are the times the
-- product sets when a record changes state, and the reports read them:
--   pm_completions.completed_at   PM compliance            service_requests.completed_at  a hailed job finished
--   logbook.closed_at             MTTR, the close audit    projects.closed_at             a project closed
--   *.approved_at (6)             who signed off, when     *.resolved_at (5)              a follow-up, signal, dispute, feedback closed
--   sensor_readings.recorded_at   when a reading was taken
-- (tools/record_time_pins.py; record_time_pin_evidence.json).
--
-- These change on purpose, so a set-once pin is wrong: the PM Scheduler upgrades today's deferred completion to done
-- and moves completed_at (pm-scheduler.html, the defer->done upgrade); a closed entry is reopened and closed again. The
-- rule that fits all of them: when a signed-in member CHANGES the time, the server's clock decides it.
--   - becoming set, or moved   -> now()          (a transition happens when the server records it)
--   - cleared to null          -> allowed        (a reopen, an approval taken back)
--   - unchanged                -> untouched
-- So a member can still close, approve, resolve and complete; what they can no longer do is choose WHEN. The service
-- role (cmms-sync, seeders, edge functions acting as the platform) is untouched: auth.uid() is null for it.
--
-- One cost, accepted: an offline close or completion that syncs later records the time it reached the server. The
-- logbook's own `date` and the phone's capture time stay on the row, and the CSV export shows both clocks.
--
-- INSERT is not touched here (an import writes historical times on purpose); the insert-time record of when the
-- server received a row is the next slice of the class (§BRH.12).

create or replace function public.wh_server_time_on_change()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
declare
  col text := tg_argv[0];
  o jsonb := to_jsonb(old);
  n jsonb := to_jsonb(new);
begin
  if auth.uid() is null or col is null then
    return new;
  end if;
  if (n -> col) is not distinct from (o -> col) then
    return new;                                           -- unchanged
  end if;
  if (n ->> col) is null then
    return new;                                           -- cleared: a reopen or an approval taken back
  end if;
  return jsonb_populate_record(new, jsonb_build_object(col, now()));   -- set or moved: the server's clock
end;
$$;

comment on function public.wh_server_time_on_change() is
  'BRH-AQ: when a signed-in caller sets or moves the state-change time named by TG_ARGV[0], it becomes now(); clearing '
  'is allowed; the service role is untouched. Gate: tools/record_time_pins.py --check.';

do $$
declare
  cell record;
  tname text;
begin
  for cell in
    select * from (values
      ('agent_followups', 'resolved_at'), ('amc_briefings', 'approved_at'), ('anomaly_signals', 'resolved_at'),
      ('asset_nodes', 'approved_at'), ('inventory_items', 'approved_at'), ('logbook', 'closed_at'),
      ('marketplace_disputes', 'resolved_at'), ('platform_feedback', 'resolved_at'), ('pm_completions', 'completed_at'),
      ('project_change_orders', 'approved_at'), ('projects', 'closed_at'), ('rcm_fmea_modes', 'approved_at'),
      ('rcm_strategies', 'approved_at'), ('sensor_readings', 'recorded_at'), ('service_requests', 'completed_at')
    ) as v(tbl, col)
  loop
    -- a table or column a fresh replay does not have yet is skipped, never an error
    if to_regclass('public.' || cell.tbl) is null
       or not exists (select 1 from pg_attribute a
                      where a.attrelid = to_regclass('public.' || cell.tbl) and a.attname = cell.col and not a.attisdropped) then
      continue;
    end if;
    tname := 'trg_server_time_' || cell.col;
    if not exists (select 1 from pg_trigger t
                   where t.tgrelid = to_regclass('public.' || cell.tbl) and t.tgname = tname) then
      execute format(
        'create trigger %I before update of %I on public.%I for each row '
        'execute function public.wh_server_time_on_change(%L)', tname, cell.col, cell.tbl, cell.col);
    end if;
  end loop;
end
$$;
