-- TB-S7-ai-write-accountability.sql
--
-- S7-ai, third cell — and the one that grades the ACT rather than the ANSWER.
--
-- The platform's AI checks all ask whether the output is good: is it grounded, is it safe, does it refuse
-- what it should. None asked WHO WROTE THE ROW. `fault_knowledge` has carried source / ai_model /
-- ai_confidence all along and nothing paired them, so both of these were accepted (probed 2026-07-31):
--   * source='ai_visual_capture' with ai_model NULL   — an AI diagnosis with no record of which model said it
--   * source='manual' with ai_model='gemini-2.0-flash' — a human entry wearing an AI badge
--
-- Why it matters more than it looks: a maintenance record is read MONTHS later by someone deciding whether
-- to trust it. "A machine suggested this" and "a technician saw this" are different claims, and a knowledge
-- base that cannot tell them apart quietly launders one into the other. Migration 20260731000006 pairs them
-- as an equivalence in BOTH directions.
--
-- The row cap is announced here because this probe writes several rows to a capped table; without it the
-- cap's 54000 masks the constraint under test and every case reads "blocked" for the wrong reason — which is
-- exactly what the first run of this probe reported.
begin;
set local workhive.row_cap_system_write = 'on';

do $probe$
declare n int; H constant uuid := '084c113b-99c0-45c6-a8e8-b4b8349da46d';
begin
  -- FORGERY 1: an AI-authored diagnosis that names no model.
  begin
    insert into public.fault_knowledge(hive_id, machine, problem, source, embedding_model)
    values (H,'TB-AI','Bearing wear detected from photo','ai_visual_capture','bge-small-en-v1.5-local');
    get diagnostics n = row_count;
    raise notice 'RESULT ai_without_model=%', case when n > 0 then 'ACCEPTED' else 'blocked' end;
  exception when others then raise notice 'RESULT ai_without_model=blocked'; end;

  -- FORGERY 2: the other direction — a human entry claiming an AI produced it.
  begin
    insert into public.fault_knowledge(hive_id, machine, problem, source, ai_model, embedding_model)
    values (H,'TB-AI2','Manual entry','manual','gemini-2.0-flash','bge-small-en-v1.5-local');
    get diagnostics n = row_count;
    raise notice 'RESULT manual_claiming_ai=%', case when n > 0 then 'ACCEPTED' else 'blocked' end;
  exception when others then raise notice 'RESULT manual_claiming_ai=blocked'; end;

  -- NON-VACUITY: both LEGITIMATE shapes must still write, or the rule is a wall rather than a contract and
  -- would simply stop the product recording AI work at all.
  begin
    insert into public.fault_knowledge(hive_id, machine, problem, source, ai_model, ai_confidence, embedding_model)
    values (H,'TB-AI3','Bearing wear detected from photo','ai_visual_capture','gemini-2.0-flash',0.87,'bge-small-en-v1.5-local');
    get diagnostics n = row_count;
    raise notice 'RESULT ai_with_model=%', case when n > 0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT ai_with_model=BLOCKED'; end;

  begin
    insert into public.fault_knowledge(hive_id, machine, problem, source, embedding_model)
    values (H,'TB-AI4','Technician observed play in the shaft','manual','bge-small-en-v1.5-local');
    get diagnostics n = row_count;
    raise notice 'RESULT manual_plain=%', case when n > 0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT manual_plain=BLOCKED'; end;
end $probe$;

rollback;
