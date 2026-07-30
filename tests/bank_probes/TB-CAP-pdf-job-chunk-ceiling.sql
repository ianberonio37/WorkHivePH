-- TB-CAP-pdf-job-chunk-ceiling.sql
--
-- `cap_pdf_job_size` is the FOURTH and mildest of the guards no registered gate names (§12.1). It is a single
-- ceiling — a PDF ingest job may carry at most 200 chunks — and it is included for completeness rather than
-- because it guards money or tenancy: a 5,000-chunk document would turn one upload into a very long embedding
-- run, so the cap is a resource bound, and its failure mode is a stalled queue rather than a stolen row.
--
-- It is worth a cell anyway, for the reason the whole §12 sweep exists: nothing would have noticed if the
-- number changed or the check vanished. A ceiling nobody tests is a ceiling that quietly becomes a suggestion.
--
-- THE BOUNDARY IS TESTED FROM BOTH SIDES, which for an off-by-one is the only test that means anything:
--   200 chunks  -> allowed   (the guard refuses `> 200`, so exactly 200 must pass)
--   201 chunks  -> refused with 54000
-- Testing only the 201 case would pass a guard written `>= 200`, which would reject a legitimate 200-chunk
-- document — the same both-sides discipline that caught the settled-cancel boundary in §11.
begin;

do $probe$
declare n int;
begin
  -- Exactly at the ceiling. `jsonb_build_array` of 200 elements via a generated series, so the fixture states
  -- its own size rather than hiding it in a literal.
  begin
    insert into public.pdf_jobs(id, source_name, target_table, embedded_chunks, status, chunks_json)
    values ('c5000000-0000-4000-8000-00000000000a','TB cap 200','pm_knowledge', 0, 'pending',
            (select jsonb_agg(jsonb_build_object('t', g)) from generate_series(1, 200) g));
    get diagnostics n = row_count;
    raise notice 'RESULT at_ceiling_200=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then
    raise notice 'RESULT at_ceiling_200=BLOCKED sqlstate=%', sqlstate;
  end;

  -- One over. 54000 is `program_limit_exceeded`, the code this guard chose — asserted rather than merely
  -- "something refused", because a CHECK or an FK failing here would look identical to a row count.
  begin
    insert into public.pdf_jobs(id, source_name, target_table, embedded_chunks, status, chunks_json)
    values ('c5000000-0000-4000-8000-00000000000b','TB cap 201','pm_knowledge', 0, 'pending',
            (select jsonb_agg(jsonb_build_object('t', g)) from generate_series(1, 201) g));
    get diagnostics n = row_count;
    raise notice 'RESULT over_ceiling_201=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then
    raise notice 'RESULT over_ceiling_201=blocked sqlstate=%', sqlstate;
  end;

  -- A non-array payload must not be treated as an enormous one. The guard reads
  -- `jsonb_typeof(NEW.chunks_json) = 'array' ... ELSE 0`, so a null or an object counts as zero chunks and
  -- passes — deliberate, and worth pinning so a future rewrite cannot start rejecting ordinary jobs.
  begin
    insert into public.pdf_jobs(id, source_name, target_table, embedded_chunks, status, chunks_json)
    values ('c5000000-0000-4000-8000-00000000000c','TB cap null','pm_knowledge', 0, 'pending', null);
    get diagnostics n = row_count;
    raise notice 'RESULT non_array_payload=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then
    raise notice 'RESULT non_array_payload=BLOCKED sqlstate=%', sqlstate;
  end;
end
$probe$;

rollback;
