-- TB-RATE-community-reply.sql
--
-- `community_reply_rate_limit` is the reply-side anti-flood: a 6th reply by the SAME author in the SAME hive
-- within 15 seconds is refused ('Replying too fast'); the first five succeed. Same recent-window shape as
-- community_post_rate_limit, with a parent post for the post_id FK. Found unscored 2026-07-31 (ARC 13 / F).
--
-- Isolated from check_daily_row_cap (well under its cap on a handful of rows); no cumulative quota on replies.
-- One transaction, so now() is fixed and every reply lands inside the 15-second window together.
begin;

insert into public.hives(id, name, invite_code, created_by)
values ('a1000000-0000-4000-8000-00000000b101'::uuid, 'TB Reply Rate Hive', 'TBRR01', 'tb-probe');
insert into public.hive_quotas(hive_id, max_rows_community, enforce_blocking)
values ('a1000000-0000-4000-8000-00000000b101'::uuid, 1000, true)
on conflict (hive_id) do update set max_rows_community = 1000, enforce_blocking = true;

insert into public.community_posts(id, hive_id, author_name, content, category)
values ('a4000000-0000-4000-8000-00000000b101'::uuid,'a1000000-0000-4000-8000-00000000b101'::uuid,
        'TB P','parent post','general');

do $probe$
declare n int;
begin
  -- five replies by the same author fit inside the window
  insert into public.community_replies(post_id, hive_id, author_name, content)
    select 'a4000000-0000-4000-8000-00000000b101'::uuid,'a1000000-0000-4000-8000-00000000b101'::uuid,'TB R','r'||g
    from generate_series(1,5) g;
  get diagnostics n = row_count;
  raise notice 'RESULT first_five=%', case when n=5 then 'allowed' else 'BLOCKED' end;

  -- the SIXTH by the same author trips the limit
  begin
    insert into public.community_replies(post_id, hive_id, author_name, content)
      values ('a4000000-0000-4000-8000-00000000b101'::uuid,'a1000000-0000-4000-8000-00000000b101'::uuid,'TB R','r6');
    get diagnostics n = row_count; raise notice 'RESULT sixth_same_author=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT sixth_same_author=blocked'; end;

  -- a DIFFERENT author is unaffected — per author, not a freeze
  begin
    insert into public.community_replies(post_id, hive_id, author_name, content)
      values ('a4000000-0000-4000-8000-00000000b101'::uuid,'a1000000-0000-4000-8000-00000000b101'::uuid,'TB R2','q1');
    get diagnostics n = row_count; raise notice 'RESULT other_author=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT other_author=BLOCKED'; end;
end $probe$;

rollback;
