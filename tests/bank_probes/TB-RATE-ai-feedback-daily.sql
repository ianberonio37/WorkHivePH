-- TB-RATE-ai-feedback-daily.sql
--
-- `enforce_ai_reply_feedback_daily_limit` caps AI-reply feedback at 200/day PER auth_uid (a null auth_uid is
-- the vetted backend path and bypasses). Found unscored 2026-07-31 (ARC 13 / F). The only trigger on the
-- table, so it is the sole refuser. 200 rows are planted for one user inside the window; the 201st trips.
begin;

insert into auth.users(id, email) values ('af000000-0000-4000-8000-00000000f101','tb-aifb@gate.local');

insert into public.ai_reply_feedback(id, auth_uid, agent, source, question, rating, created_at)
select gen_random_uuid(), 'af000000-0000-4000-8000-00000000f101'::uuid, 'james', 'chat', 'q'||g, 1, now()
from generate_series(1,200) g;

do $probe$
declare n int;
begin
  -- the 201st for this user trips the daily cap
  begin
    insert into public.ai_reply_feedback(auth_uid, agent, source, question, rating)
      values ('af000000-0000-4000-8000-00000000f101'::uuid, 'james', 'chat', 'q201', 1);
    get diagnostics n = row_count; raise notice 'RESULT over_cap=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT over_cap=blocked'; end;

  -- the vetted backend path (auth_uid NULL) bypasses the cap
  begin
    insert into public.ai_reply_feedback(auth_uid, agent, source, question, rating)
      values (null, 'james', 'chat', 'backend', 1);
    get diagnostics n = row_count; raise notice 'RESULT backend_bypass=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT backend_bypass=BLOCKED'; end;
end $probe$;

rollback;
