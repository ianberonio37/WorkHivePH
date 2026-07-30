-- TB-IMG-inline-image-cap.sql
--
-- `check_inline_image_size` caps an inline base64 photo at 1.5 MB (octet_length) on logbook and
-- inventory_items, so one oversized data-URL cannot bloat a row (and every list query that reads it). A
-- resource bound, not a tenancy/money guard — its failure mode is a heavy row, not a stolen one — but a cap
-- nobody tests quietly becomes a suggestion.
--
-- Found unscored 2026-07-31 (ARC 13 / F). The guard has no auth branch, so it applies to every caller; the row
-- is planted as postgres (which also bypasses the logbook quota/rate-limit triggers that DO check auth), so
-- what refuses the oversized photo is unambiguously THIS trigger. Tested from both sides: just over the cap is
-- refused, an ordinary small photo is allowed.
begin;

do $probe$
declare n int;
begin
  -- ~1.6 MB base64 string: over the 1.5 MB cap. The fixture states its own size via repeat().
  begin
    insert into public.logbook(worker_name, date, photo)
      values ('TB Img', current_date, repeat('A', 1600000));
    get diagnostics n=row_count; raise notice 'RESULT over_cap=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT over_cap=blocked sqlstate=%', sqlstate; end;

  -- an ordinary small photo is allowed — the write that separates 'caps huge images' from 'rejects photos'.
  begin
    insert into public.logbook(worker_name, date, photo)
      values ('TB Img', current_date, repeat('A', 1000));
    get diagnostics n=row_count; raise notice 'RESULT under_cap=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT under_cap=BLOCKED sqlstate=%', sqlstate; end;
end $probe$;

rollback;
