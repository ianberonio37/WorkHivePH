-- TB-RATE-community-post.sql
--
-- `community_post_rate_limit` is a short-window anti-flood: a 4th post by the SAME author in the SAME hive
-- within 30 seconds is refused ('Posting too fast'). It counts EXISTING posts in the window, so three succeed
-- and the fourth trips. A whole probe runs in one transaction, where now() is fixed at transaction start, so
-- every insert lands inside the 30-second window together.
--
-- Found unscored 2026-07-31 (ARC 13 / F). Isolated from the cumulative community quota by pinning
-- max_rows_community high (a fresh hive, cap 1000), and from check_daily_row_cap (200/hive) by staying well
-- under it; the rate limit has no auth branch, so it is planted as postgres and IS the sole refuser at the 4th.
begin;

insert into public.hives(id, name, invite_code, created_by)
values ('a1000000-0000-4000-8000-00000000b001'::uuid, 'TB Rate Community Hive', 'TBRC01', 'tb-probe');
insert into public.hive_quotas(hive_id, max_rows_community, enforce_blocking)
values ('a1000000-0000-4000-8000-00000000b001'::uuid, 1000, true)
on conflict (hive_id) do update set max_rows_community = 1000, enforce_blocking = true;

do $probe$
declare n int;
begin
  -- three posts by the same author fit inside the window
  insert into public.community_posts(hive_id, author_name, content, category)
    values ('a1000000-0000-4000-8000-00000000b001'::uuid,'TB R','p1','general'),
           ('a1000000-0000-4000-8000-00000000b001'::uuid,'TB R','p2','general'),
           ('a1000000-0000-4000-8000-00000000b001'::uuid,'TB R','p3','general');
  get diagnostics n = row_count;
  raise notice 'RESULT first_three=%', case when n=3 then 'allowed' else 'BLOCKED' end;

  -- the FOURTH by the same author trips the limit
  begin
    insert into public.community_posts(hive_id, author_name, content, category)
      values ('a1000000-0000-4000-8000-00000000b001'::uuid,'TB R','p4','general');
    get diagnostics n = row_count; raise notice 'RESULT fourth_same_author=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT fourth_same_author=blocked'; end;

  -- a DIFFERENT author is unaffected — the limit is per author, not a freeze
  begin
    insert into public.community_posts(hive_id, author_name, content, category)
      values ('a1000000-0000-4000-8000-00000000b001'::uuid,'TB R2','q1','general');
    get diagnostics n = row_count; raise notice 'RESULT other_author=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT other_author=BLOCKED'; end;
end $probe$;

rollback;
