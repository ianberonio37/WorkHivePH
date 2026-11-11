-- BRH-AQ (2026-11-11): a record keeps the time it was made.
--
-- Found by the M13 claim audit of the guide "start a digital logbook in a Philippine factory", which tells a plant that
-- an auditor's first question is "can the entry be backdated?" and that the answer must be no. Measured on the local
-- stack: a worker, signed in, sent
--     update logbook set created_at = '2020-01-01' where id = <their own open entry>
-- through the API and it held. Nothing recorded it.
--
-- Supabase grants `authenticated` UPDATE on every column, so on every table a member may update, created_at was
-- writable: 70 tables (tools/record_time_pins.py; record_time_pin_evidence.json holds the population as measured).
-- created_at is the record's birth time and nothing in the product updates it - no page, no edge function, no SQL
-- (checked 2026-11-11) - so it is pinned: for a signed-in caller an UPDATE puts the old value back. The service role
-- (seeders, edge functions acting as the platform, pg_cron, migrations) keeps the right to repair data, because
-- auth.uid() is null for it.
--
-- The trigger fires only when created_at is in the SET list (BEFORE UPDATE OF created_at), so ordinary edits pay
-- nothing. The value is put back rather than refused: an upsert that carries the row's original created_at (an
-- offline merge) must keep working, and keeping the old value is the same answer either way.
--
-- Inserts are not touched: an import of a CMMS's history writes the source system's created_at on purpose, and the
-- Weibull, P-F and FMEA fitters read it as the failure time. The domain times a report reads (pm_completions.completed_at,
-- logbook.closed_at, the approved_at and resolved_at columns) change on a state transition and are fixed table by
-- table under the same class; the gate record-time-pins holds them forward-only until then.

create or replace function public.wh_pin_created_at()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  if auth.uid() is not null and new.created_at is distinct from old.created_at then
    new.created_at := old.created_at;
  end if;
  return new;
end;
$$;

comment on function public.wh_pin_created_at() is
  'BRH-AQ: a signed-in caller cannot move a record''s created_at; the service role can. Attached as trg_pin_created_at '
  'to every public table where authenticated holds UPDATE on created_at. Gate: tools/record_time_pins.py --check.';

do $$
declare r record;
begin
  -- MATERIALIZED: the table filter must run before has_column_privilege, which raises on an index (an index can carry
  -- a created_at attribute - service_credit_ledger_pkey does - and the planner may evaluate the call first otherwise).
  for r in
    with tables as materialized (
      select c.oid, c.relname
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
      where n.nspname = 'public'
        and c.relkind = 'r'
        and exists (select 1 from pg_attribute a
                    where a.attrelid = c.oid and a.attname = 'created_at' and not a.attisdropped)
    )
    select oid, relname from tables
    where has_column_privilege('authenticated', oid, 'created_at', 'UPDATE')
  loop
    if not exists (select 1 from pg_trigger t where t.tgrelid = r.oid and t.tgname = 'trg_pin_created_at') then
      execute format(
        'create trigger trg_pin_created_at before update of created_at on public.%I '
        'for each row execute function public.wh_pin_created_at()', r.relname);
    end if;
  end loop;
end
$$;
