-- SL LB2 (2026-10-20): READS NO INDEX COULD FIX - THE SHAPES THAT KEPT THEM OFF ONE.
--
-- 20261020000001 gave 42 reads the index they lacked. What still read a growing table end to end did so because of its
-- SHAPE, not a missing index - measured as each page's cast, RLS on, with the tables grown from their own rows inside a
-- rolled-back transaction (50k-130k rows on the history tables, ~100x the hives, people and assets):
--   * a filter on a per-row SECURITY DEFINER call - `is_mine = true` / `to_me` / `from_me` called listing_is_mine() or
--     inquiry_is_from_me() once per listing / inquiry on the platform (0.5-1.3 s at 56k listings, 30k inquiries);
--   * an OR around a hashed subplan, which no index can serve - my_service_provider_ids() read all 7,007 providers, and
--     every balance and policy that asks it paid for that;
--   * an aggregate built before the page's filter could narrow it - v_service_provider_truth grouped every request and
--     review on the platform, get_hive_trade_peers grouped every badge;
--   * a policy function called once per row - analytics_events_select_admin: 33,922 is_platform_admin() calls, 6.3 s;
--   * a platform total summed from every ledger entry ever written (2.3-4.7 s at 13k entries);
--   * and under all of them: a policy comparing against a BARE auth.uid(). Under RLS that comparison cannot become an
--     index condition (the call is inlined per row and is not leakproof), so every "my hives" check read ALL of
--     hive_members - 2,625 rows removed to keep one or two, 3.5 ms each, against 0.037 ms on idx_hive_members_auth_uid
--     with `(select auth.uid())`. Costed at a full read per check, the planner then hashed whole tables (all 12,423 PM
--     assets, all 10,302 inventory items) to answer a page about one hive. The LB2 inventory never flagged it: it grew
--     hive_members to 2,626 rows, under the 5,000-row line that marks a grown table - the one table every policy reads.
--
-- EVERY REWRITE BELOW LEAVES EVERY READER'S ROWS AS THEY WERE. Proven with tools/prove_rewrite_equivalence.py: in one
-- rolled-back transaction, as every account plus anon and a signed-in stranger, each affected relation is fingerprinted
-- (row count + md5 over every row) before and after the rewrite, with the edge rows a rewrite could treat differently
-- seeded first (a soft-deleted parent, a NULL key, a scope item or transaction filed under another hive than its asset's
-- or item's, a listing with no owner, an inquiry with no listing ...). The tool has teeth: an earlier proposal for the PM
-- scope policy - key it on pm_scope_items.hive_id - was caught showing 4 accounts 6 extra rows, and is not what ships.
-- my_recent_xp(30) was checked row for row and in order against the direct read it replaces, for every account.
--
-- MEASURED, NOT ASSUMED: every one of the 576 distinct reads the LB2 inventory holds (and the page RPCs) was EXPLAIN
-- ANALYZEd at grown size as its cast before and after, each run twice and the warm run compared. Two rewrites that were
-- proven equivalent were dropped because they were slower: pm_scope_items_read as a correlated EXISTS ran per row for
-- every row the write policy rejected (52 -> 519 ms on the day planner), and the one-array form on every inventory
-- policy made a single-row lookup 3-9x slower before the auth.uid() wrap made membership checks cheap.
--
-- TWO THINGS THAT LOOK LIKE THE FIX AND ARE NOT:
--   * `is_mine = (l.auth_uid = auth.uid())` inline: the reader has no SELECT on marketplace_listings.auth_uid or
--     marketplace_inquiries.buyer_auth_uid (column grants hide them), so a security_invoker view naming them fails with
--     permission denied. The reader's own ids come from SECURITY DEFINER sets scoped to auth.uid() instead.
--   * CREATE OR REPLACE VIEW without its WITH (security_invoker = ...) clause: the new options list REPLACES the old
--     one even when empty, silently turning an invoker view into an owner view that reads with RLS off. Every view
--     below restates its option.
--
-- Held by the query-indexes gate (tools/validate_query_indexes.py): each object's last definition keeps its measured
-- shape, no policy compares against a bare auth.uid() (and no later migration may add one), the kept credit totals
-- reconcile with the ledger, and the shapes are probed at grown size on every run.

-- 1. analytics_events_select_admin - is_platform_admin() takes no column: asked as a scalar subquery it is an InitPlan, run
-- once per statement; written bare, the planner called the SECURITY DEFINER function once per row (33,922 calls in
-- founder_dau_series at 152k events).
drop policy if exists analytics_events_select_admin on public.analytics_events;
create policy analytics_events_select_admin on public.analytics_events as permissive for select to authenticated
  using ((select public.is_platform_admin()));

-- 2. is_mine / to_me / from_me - "is this mine?" was a SECURITY DEFINER call per row (listing_is_mine, inquiry_is_from_me),
-- so a page asking for `is_mine = true` read every listing and every inquiry. The reader cannot see auth_uid or
-- buyer_auth_uid (column grants hide them), so the views cannot compare those columns themselves: the reader's own ids
-- come from two SECURITY DEFINER sets scoped to auth.uid(), asked ONCE per statement (an InitPlan), and
-- `id = ANY($1)` is an index condition on the primary key / listing_id.
create or replace function public.my_listing_ids()
returns setof uuid
language sql
stable
security definer
set search_path = public
as $$
  select l.id from public.marketplace_listings l where auth.uid() is not null and l.auth_uid = auth.uid()
$$;
revoke all on function public.my_listing_ids() from public;
grant execute on function public.my_listing_ids() to anon, authenticated, service_role;

create or replace function public.my_inquiry_ids()
returns setof uuid
language sql
stable
security definer
set search_path = public
as $$
  select i.id from public.marketplace_inquiries i where auth.uid() is not null and i.buyer_auth_uid = auth.uid()
$$;
revoke all on function public.my_inquiry_ids() from public;
grant execute on function public.my_inquiry_ids() to anon, authenticated, service_role;

create or replace view public.v_marketplace_listings_truth with (security_invoker = on) as
 SELECT l.id,
    l.hive_id,
    l.seller_name,
    l.seller_contact,
    COALESCE(ms.kyb_verified, false) OR COALESCE(ms.cert_verified, false) AS seller_verified,
    COALESCE(ms.total_sales, 0) AS completed_sales,
    ms.rating_avg,
    l.section,
    l.category,
    l.title,
    l.description,
    l.price,
    l.condition,
    l.location,
    l.image_url,
    l.status,
    l.view_count,
    l.created_at,
    l.updated_at,
    ms.tier AS seller_tier,
    ms.kyb_verified AS seller_kyb_verified,
    ms.total_sales AS seller_total_sales,
    ms.rating_avg AS seller_rating_avg_live,
    ms.rating_count AS seller_rating_count,
    ms.response_rate AS seller_response_rate,
    ms.response_time_h AS seller_response_time_h,
    l.status = 'published'::text AS is_published,
    l.status = 'sold'::text AS is_sold,
    l.status = 'draft'::text AS is_draft,
    l.part_number,
    l.moderation_reason,
    l.moderated_at,
    l.moderated_by,
    l.id = ANY (ARRAY( SELECT public.my_listing_ids())) AS is_mine
   FROM marketplace_listings l
     LEFT JOIN marketplace_sellers ms ON ms.worker_name = l.seller_name;

create or replace view public.v_marketplace_inquiries_truth with (security_invoker = true) as
 SELECT i.id,
    i.listing_id,
    i.hive_id,
    i.buyer_name,
    i.buyer_contact,
    i.seller_name,
    i.message,
    i.reply_text,
    i.replied_at,
    i.status,
    i.created_at,
    l.title AS listing_title,
    l.section AS listing_section,
    l.price AS listing_price,
    l.status AS listing_status,
    i.status = 'pending'::text AS is_pending,
    i.status = 'replied'::text AS is_replied,
    i.status = 'closed'::text AS is_closed,
    (i.listing_id IS NOT NULL AND i.listing_id = ANY (ARRAY( SELECT public.my_listing_ids()))) AS to_me,
    i.id = ANY (ARRAY( SELECT public.my_inquiry_ids())) AS from_me
   FROM marketplace_inquiries i
     LEFT JOIN marketplace_listings l ON l.id = i.listing_id;

-- v_marketplace_listings_public runs as its owner (no security_invoker - it filters its own rows), so it may compare
-- auth_uid itself; the COALESCE only hid the column from the index. Same value: true only when both are set and equal.
create or replace view public.v_marketplace_listings_public as
 SELECT l.id,
    l.hive_id,
    l.seller_name,
    COALESCE(ms.kyb_verified, false) OR COALESCE(ms.cert_verified, false) AS seller_verified,
    COALESCE(ms.total_sales, 0) AS completed_sales,
    ms.rating_avg,
    l.section,
    l.category,
    l.title,
    l.description,
    l.price,
    l.condition,
    l.location,
    l.image_url,
    l.status,
    l.view_count,
    l.created_at,
    l.updated_at,
    ms.tier AS seller_tier,
    ms.kyb_verified AS seller_kyb_verified,
    ms.total_sales AS seller_total_sales,
    ms.rating_avg AS seller_rating_avg_live,
    ms.rating_count AS seller_rating_count,
    ms.response_rate AS seller_response_rate,
    ms.response_time_h AS seller_response_time_h,
    l.status = 'published'::text AS is_published,
    l.status = 'sold'::text AS is_sold,
    l.status = 'draft'::text AS is_draft,
    l.part_number,
    (auth.uid() IS NOT NULL AND l.auth_uid IS NOT NULL AND l.auth_uid = auth.uid()) AS is_mine,
    l.ai_assisted_fields
   FROM marketplace_listings l
     LEFT JOIN marketplace_sellers ms ON ms.worker_name = l.seller_name
  WHERE l.status = 'published'::text OR l.auth_uid = auth.uid();

-- 3. my_service_provider_ids() - `auth_uid = me OR (hive provider AND hive_id IN (my hives))` is an OR around a hashed
-- subplan: no index can answer it, so every provider on the platform was read (and every policy and balance that asks
-- "which providers are mine?" paid for it). The two arms as a UNION each ride an index - the reader's own profiles on the
-- new auth_uid index, the hive's profiles through the reader's memberships on service_providers_hive_id.
create index if not exists idx_service_providers_auth_uid on public.service_providers (auth_uid) where auth_uid is not null;

create or replace function public.my_service_provider_ids()
returns setof uuid
language sql
stable
security definer
set search_path to 'pg_catalog', 'public'
as $$
  select sp.id from public.service_providers sp
   where sp.auth_uid = auth.uid()
  union
  select sp.id from public.service_providers sp
   where sp.provider_type = 'hive'
     and sp.hive_id in (select hm.hive_id from public.hive_members hm
                         where hm.auth_uid = auth.uid() and hm.status = 'active');
$$;

-- 4. v_service_provider_truth - the job count and the rating were two GROUP BYs over every request and every review on the
-- platform, built before the page's `id = ANY(...)` could narrow them. Asked per provider (LATERAL), each is a lookup on
-- service_requests_provider. An aggregate with no GROUP BY always answers one row, so a provider with no jobs gets 0 and
-- no rating exactly as the LEFT JOIN to a missing group did (COALESCE(.., 0) / NULL average).
create or replace view public.v_service_provider_truth with (security_invoker = on) as
 SELECT sp.id,
    sp.provider_type,
    sp.worker_name,
    sp.hive_id,
    sp.display_name,
    sp.contact,
    sp.categories,
    sp.service_areas,
    sp.base_lat,
    sp.base_lng,
    sp.availability,
    sp.verified,
    sp.verified_at,
    sp.created_at,
    COALESCE(j.completed_jobs, 0::bigint) AS completed_jobs,
    rv.rating_avg,
    COALESCE(rv.rating_count, 0::bigint) AS rating_count,
        CASE
            WHEN COALESCE(j.completed_jobs, 0::bigint) >= 25 AND COALESCE(rv.rating_avg, 0::numeric) >= 4.5 THEN 'gold'::text
            WHEN COALESCE(j.completed_jobs, 0::bigint) >= 10 THEN 'silver'::text
            ELSE 'bronze'::text
        END AS tier,
    1 AS _source_count,
    sp.updated_at AS _freshness_ts,
    'service_provider_truth:v3'::text AS _canonical_version
   FROM service_providers sp
     LEFT JOIN LATERAL ( SELECT count(*) AS completed_jobs
           FROM service_requests sr
          WHERE sr.matched_provider_id = sp.id
            AND sr.status = ANY (ARRAY['completed'::text, 'settled'::text])) j ON true
     LEFT JOIN LATERAL ( SELECT round(avg(mr.rating), 2) AS rating_avg,
            count(*) AS rating_count
           FROM marketplace_reviews mr
             JOIN service_requests r ON r.id = mr.request_id
          WHERE r.matched_provider_id = sp.id
            AND mr.direction = 'client_to_provider'::text) rv ON true;

-- 5. get_hive_trade_peers - its lvl CTE took every Practitioner+ badge on the platform (a Seq Scan on skill_badges) and only
-- then joined the hive. Both readers of lvl (my_trades: the caller; the final join: the hive's active peers) are active
-- members of p_hive_id, so lvl is narrowed to those auth_uids first - idx_skill_badges_auth_uid per member.
CREATE OR REPLACE FUNCTION public.get_hive_trade_peers(p_hive_id uuid)
 RETURNS TABLE(worker_name text, role text, shared_disciplines jsonb)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  WITH caller AS (
    -- authorization gate: the auth'd user must be an active member of this hive
    SELECT hm.auth_uid
    FROM public.hive_members hm
    WHERE hm.hive_id = p_hive_id
      AND hm.auth_uid = auth.uid()
      AND hm.status = 'active'
    LIMIT 1
  ),
  lvl AS (
    -- max badge level per (person, discipline); Practitioner+ only = a real "trade" - for this hive's active members
    -- only (the caller and the peers are the only people the result can name)
    SELECT sb.auth_uid, sb.discipline, max(sb.level) AS level
    FROM public.skill_badges sb
    WHERE sb.level >= 2
      AND sb.auth_uid IN (SELECT m.auth_uid FROM public.hive_members m
                           WHERE m.hive_id = p_hive_id AND m.status = 'active' AND m.auth_uid IS NOT NULL)
    GROUP BY sb.auth_uid, sb.discipline
  ),
  my_trades AS (
    SELECT l.discipline
    FROM lvl l JOIN caller c ON l.auth_uid = c.auth_uid
  ),
  peers AS (
    -- other active members of THIS hive (spoof-safe: matched later by auth_uid)
    SELECT hm.worker_name, hm.role, hm.auth_uid
    FROM public.hive_members hm CROSS JOIN caller c
    WHERE hm.hive_id = p_hive_id
      AND hm.status = 'active'
      AND hm.auth_uid IS NOT NULL
      AND hm.auth_uid IS DISTINCT FROM c.auth_uid
  )
  SELECT
    p.worker_name,
    p.role,
    jsonb_agg(jsonb_build_object('discipline', l.discipline, 'level', l.level)
              ORDER BY l.level DESC, l.discipline) AS shared_disciplines
  FROM peers p
  JOIN lvl l       ON l.auth_uid = p.auth_uid          -- peer's Practitioner+ trades
  JOIN my_trades m ON m.discipline = l.discipline       -- ...that overlap MY trades
  GROUP BY p.worker_name, p.role
  ORDER BY max(l.level) DESC, p.worker_name;
$function$;

-- 6. The credit position's totals. A marketplace admin's get_credit_ledger_totals() summed every ledger entry ever
--    written - correct (it replaced a browser sum over a 2,000-row cap) but it reads more with every credit that moves.
--    The ledger is append-only in practice (nine SECURITY DEFINER writers insert; no function updates or deletes), so its
--    totals are kept as it is written - the same way credit_treasury keeps issuance: one row per entry type, maintained
--    by an AFTER trigger that also follows the service-role UPDATE / DELETE / TRUNCATE a repair could make. The gate
--    query-indexes reconciles these totals against the ledger on every run, so a drift cannot hide.
create table if not exists public.service_credit_ledger_totals (
  entry_type text primary key,
  total      numeric     not null default 0,
  entries    bigint      not null default 0,
  updated_at timestamptz not null default now()
);
comment on table public.service_credit_ledger_totals is
  'SL LB2 2026-10-20: the credit ledger''s totals per entry type, kept by trg_keep_ledger_totals as the ledger is written; reconciled by the query-indexes gate.';
alter table public.service_credit_ledger_totals enable row level security;
revoke all on public.service_credit_ledger_totals from public, anon, authenticated;
grant select on public.service_credit_ledger_totals to authenticated;
grant all on public.service_credit_ledger_totals to service_role;
drop policy if exists service_credit_ledger_totals_admin_read on public.service_credit_ledger_totals;
create policy service_credit_ledger_totals_admin_read on public.service_credit_ledger_totals
  as permissive for select to authenticated
  using ((select public.is_marketplace_admin()));

create or replace function public.keep_service_credit_ledger_totals()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'TRUNCATE' then
    delete from public.service_credit_ledger_totals;
    return null;
  end if;
  if tg_op in ('UPDATE', 'DELETE') then
    update public.service_credit_ledger_totals
       set total = total - old.amount, entries = entries - 1, updated_at = now()
     where entry_type = old.entry_type;
  end if;
  if tg_op in ('INSERT', 'UPDATE') then
    insert into public.service_credit_ledger_totals as t (entry_type, total, entries)
    values (new.entry_type, new.amount, 1)
    on conflict (entry_type) do update
      set total = t.total + excluded.total, entries = t.entries + 1, updated_at = now();
  end if;
  return null;
end
$$;
revoke all on function public.keep_service_credit_ledger_totals() from public, anon, authenticated;

drop trigger if exists trg_keep_ledger_totals on public.service_credit_ledger;
create trigger trg_keep_ledger_totals
  after insert or update or delete on public.service_credit_ledger
  for each row execute function public.keep_service_credit_ledger_totals();
drop trigger if exists trg_keep_ledger_totals_truncate on public.service_credit_ledger;
create trigger trg_keep_ledger_totals_truncate
  after truncate on public.service_credit_ledger
  for each statement execute function public.keep_service_credit_ledger_totals();

-- seed from the ledger as it stands; the lock keeps a concurrent writer from landing between the seed and the trigger
lock table public.service_credit_ledger in share row exclusive mode;
delete from public.service_credit_ledger_totals;
insert into public.service_credit_ledger_totals (entry_type, total, entries)
select l.entry_type, sum(l.amount), count(*) from public.service_credit_ledger l group by l.entry_type;

create or replace function public.get_credit_ledger_totals()
returns table (entry_type text, total numeric, entries bigint, unreadable bigint)
language sql
stable
security invoker
set search_path = public
as $$
  -- a marketplace admin: the totals the ledger keeps as it is written (a handful of rows, whatever the ledger's size)
  select t.entry_type, t.total, t.entries, 0::bigint
    from public.service_credit_ledger_totals t
   where (select public.is_marketplace_admin()) and t.entries > 0
  union all
  -- anyone else: their own accounts' entries, found on service_credit_ledger_account
  select l.entry_type, sum(l.amount), count(*), count(*) filter (where l.amount is null)
    from public.service_credit_ledger l
   where not (select public.is_marketplace_admin())
     and ((l.account_type = 'consumer' and l.account_id = (select auth.uid()))
          or (l.account_type = 'provider' and l.account_id = any (array(select public.my_service_provider_ids()))))
   group by l.entry_type
$$;
revoke all on function public.get_credit_ledger_totals() from public, anon;
grant execute on function public.get_credit_ledger_totals() to authenticated;

-- 7. my_recent_xp - achievements' "Recent activity" read achievement_xp_log with no filter (RLS scopes it to the
--     reader's names) ordered by earned_at: the planner cannot know how many of the platform's recent rows are the
--     reader's, so it walks idx_xp_log_earned through everyone's history until 30 of theirs turn up (46,324 rows
--     removed at grown size). Asked per name - each of the reader's names, its own 30 newest on idx_xp_log_worker
--     (worker_name, earned_at DESC) - and merged, the read costs (names x 30) whatever the platform's size. SECURITY
--     INVOKER: the table's own policy (ach_log_owner_read) still decides every row, exactly as for the direct read.
create or replace function public.my_recent_xp(p_limit integer default 30)
returns table (achievement_id text, xp_earned integer, source_action text, earned_at timestamptz)
language sql
stable
security invoker
set search_path = public
as $$
  select x.achievement_id, x.xp_earned, x.source_action, x.earned_at
    from unnest(array(select public.auth_worker_names())) n(name)
    cross join lateral (
      select l.id, l.achievement_id, l.xp_earned, l.source_action, l.earned_at
        from public.achievement_xp_log l
       where l.worker_name = n.name
       order by l.earned_at desc, l.id
       limit greatest(1, least(coalesce(p_limit, 30), 200))
    ) x
   order by x.earned_at desc, x.id
   limit greatest(1, least(coalesce(p_limit, 30), 200))
$$;
revoke all on function public.my_recent_xp(integer) from public, anon;
grant execute on function public.my_recent_xp(integer) to authenticated;

-- 8. Every policy that compared against a bare auth.uid() asks it ONCE per statement: `( SELECT auth.uid() AS uid)` is an
--    InitPlan, so `hm.auth_uid = $1` is an index condition on idx_hive_members_auth_uid. auth.uid() is STABLE - the
--    value is the one the bare call returned. 480 calls in 225 policies on 125 tables, regenerated from the
--    database as the migrations built it (static CREATE POLICY and the ones migrations create in loops alike):
--    USING, WITH CHECK, command, roles and permissive/restrictive are carried over as they were; only the call's form
--    changes. In the two parent tables' policies (pm_assets, inventory_items) and the FOR ALL write policies that ask
--    them (pm_scope_items_write, inventory_transactions_write), the reader's hives are also asked as ONE array -
--    `hive_id = ANY (ARRAY(SELECT ...))`, an index condition where `IN (SELECT ...)` was a hashed subplan the planner
--    could not estimate (it expected 9,145 visible assets; 17 were) and so hashed the whole table. Same truth value for
--    every row, NULLs included. Proven per reader on all 125 tables, with the edge rows seeded.
drop policy if exists aem_read on public.agent_episodic_memory;
create policy aem_read on public.agent_episodic_memory as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists followups_read on public.agent_followups;
create policy followups_read on public.agent_followups as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = agent_followups.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists agent_memory_delete on public.agent_memory;
create policy agent_memory_delete on public.agent_memory as permissive for DELETE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists agent_memory_insert on public.agent_memory;
create policy agent_memory_insert on public.agent_memory as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists agent_memory_insert_own on public.agent_memory;
create policy agent_memory_insert_own on public.agent_memory as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) = worker_id) OR (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists agent_memory_read on public.agent_memory;
create policy agent_memory_read on public.agent_memory as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((( SELECT auth.uid() AS uid) = auth_uid) OR (( SELECT auth.uid() AS uid) = worker_id))));
drop policy if exists agent_memory_update on public.agent_memory;
create policy agent_memory_update on public.agent_memory as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists agent_memory_worker_access on public.agent_memory;
create policy agent_memory_worker_access on public.agent_memory as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) = worker_id) OR (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists agentic_rag_traces_read on public.agentic_rag_traces;
create policy agentic_rag_traces_read on public.agentic_rag_traces as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (is_platform_admin() OR ((hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = agentic_rag_traces.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text))))))));
drop policy if exists ai_audit_log_hive_insert on public.ai_audit_log;
create policy ai_audit_log_hive_insert on public.ai_audit_log as permissive for INSERT to authenticated
  with check ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists ai_audit_log_hive_select on public.ai_audit_log;
create policy ai_audit_log_hive_select on public.ai_audit_log as permissive for SELECT to authenticated
  using ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists ai_cost_log_read on public.ai_cost_log;
create policy ai_cost_log_read on public.ai_cost_log as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (is_platform_admin() OR (auth_uid = ( SELECT auth.uid() AS uid)) OR ((hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = ai_cost_log.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text))))))));
drop policy if exists ai_knowledge_gap_hive_all on public.ai_knowledge_gap;
create policy ai_knowledge_gap_hive_all on public.ai_knowledge_gap as permissive for ALL to authenticated
  using ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))))
  with check ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists ai_quality_escalation_hive_all on public.ai_quality_escalation;
create policy ai_quality_escalation_hive_all on public.ai_quality_escalation as permissive for ALL to authenticated
  using ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))))
  with check ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists ai_quality_log_read on public.ai_quality_log;
create policy ai_quality_log_read on public.ai_quality_log as permissive for SELECT to public
  using ((( SELECT auth.uid() AS uid) IS NOT NULL));
drop policy if exists ai_reply_feedback_insert on public.ai_reply_feedback;
create policy ai_reply_feedback_insert on public.ai_reply_feedback as permissive for INSERT to authenticated
  with check (((auth_uid = ( SELECT auth.uid() AS uid)) AND ((hive_id IS NULL) OR (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = ai_reply_feedback.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))));
drop policy if exists ai_reply_feedback_read on public.ai_reply_feedback;
create policy ai_reply_feedback_read on public.ai_reply_feedback as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((( SELECT auth.uid() AS uid) = auth_uid) OR ((hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = ai_reply_feedback.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))));
drop policy if exists ai_reports_read on public.ai_reports;
create policy ai_reports_read on public.ai_reports as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE ((hive_members.auth_uid = ( SELECT auth.uid() AS uid)) AND (hive_members.status = 'active'::text))))));
drop policy if exists ai_user_rate_limits_own on public.ai_user_rate_limits;
create policy ai_user_rate_limits_own on public.ai_user_rate_limits as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (user_id = (( SELECT auth.uid() AS uid))::text)));
drop policy if exists alert_dismissals_member_delete on public.alert_dismissals;
create policy alert_dismissals_member_delete on public.alert_dismissals as permissive for DELETE to authenticated
  using ((EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = alert_dismissals.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))));
drop policy if exists alert_dismissals_member_read on public.alert_dismissals;
create policy alert_dismissals_member_read on public.alert_dismissals as permissive for SELECT to authenticated
  using ((EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = alert_dismissals.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))));
drop policy if exists alert_dismissals_member_update on public.alert_dismissals;
create policy alert_dismissals_member_update on public.alert_dismissals as permissive for UPDATE to authenticated
  using ((EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = alert_dismissals.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))
  with check ((EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = alert_dismissals.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))));
drop policy if exists alert_dismissals_member_write on public.alert_dismissals;
create policy alert_dismissals_member_write on public.alert_dismissals as permissive for INSERT to authenticated
  with check ((EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = alert_dismissals.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))));
drop policy if exists amc_briefings_read on public.amc_briefings;
create policy amc_briefings_read on public.amc_briefings as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists amc_briefings_update_supervisor on public.amc_briefings;
create policy amc_briefings_update_supervisor on public.amc_briefings as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = amc_briefings.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = amc_briefings.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))));
drop policy if exists analytics_snapshots_member_read on public.analytics_snapshots;
create policy analytics_snapshots_member_read on public.analytics_snapshots as permissive for SELECT to authenticated
  using ((EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = analytics_snapshots.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))));
drop policy if exists anomaly_alerts_hive_access on public.anomaly_alerts;
create policy anomaly_alerts_hive_access on public.anomaly_alerts as permissive for SELECT to public
  using ((EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = anomaly_alerts.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))));
drop policy if exists anomaly_signals_read on public.anomaly_signals;
create policy anomaly_signals_read on public.anomaly_signals as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists anomaly_signals_update_supervisor on public.anomaly_signals;
create policy anomaly_signals_update_supervisor on public.anomaly_signals as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = anomaly_signals.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = anomaly_signals.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))));
drop policy if exists api_keys_supervisor_all on public.api_keys;
create policy api_keys_supervisor_all on public.api_keys as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = api_keys.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = api_keys.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))));
drop policy if exists asset_edges_read on public.asset_edges;
create policy asset_edges_read on public.asset_edges as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists asset_edges_write on public.asset_edges;
create policy asset_edges_write on public.asset_edges as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = asset_edges.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists asset_embeddings_read on public.asset_embeddings;
create policy asset_embeddings_read on public.asset_embeddings as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists asset_nodes_read on public.asset_nodes;
create policy asset_nodes_read on public.asset_nodes as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))));
drop policy if exists asset_nodes_write on public.asset_nodes;
create policy asset_nodes_write on public.asset_nodes as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR ((auth_uid = ( SELECT auth.uid() AS uid)) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))) OR (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = asset_nodes.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text)))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))));
drop policy if exists asset_risk_scores_read on public.asset_risk_scores;
create policy asset_risk_scores_read on public.asset_risk_scores as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists asset_watchlist_hive_all on public.asset_watchlist;
create policy asset_watchlist_hive_all on public.asset_watchlist as permissive for ALL to authenticated
  using ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))))
  with check ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists auth_session_events_read on public.auth_session_events;
create policy auth_session_events_read on public.auth_session_events as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((( SELECT auth.uid() AS uid) = auth_uid) OR (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = auth_session_events.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text)))))));
drop policy if exists automation_log_read on public.automation_log;
create policy automation_log_read on public.automation_log as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE ((hive_members.auth_uid = ( SELECT auth.uid() AS uid)) AND (hive_members.status = 'active'::text))))));
drop policy if exists avatar_state_owner_read on public.avatar_state;
create policy avatar_state_owner_read on public.avatar_state as permissive for SELECT to authenticated
  using ((auth_uid = ( SELECT auth.uid() AS uid)));
drop policy if exists avatar_state_owner_rw on public.avatar_state;
create policy avatar_state_owner_rw on public.avatar_state as permissive for ALL to authenticated
  using ((auth_uid = ( SELECT auth.uid() AS uid)))
  with check ((auth_uid = ( SELECT auth.uid() AS uid)));
drop policy if exists bom_knowledge_hive_rw on public.bom_knowledge;
create policy bom_knowledge_hive_rw on public.bom_knowledge as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists calc_knowledge_hive_rw on public.calc_knowledge;
create policy calc_knowledge_hive_rw on public.calc_knowledge as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists cps_read on public.canonical_period_summaries;
create policy cps_read on public.canonical_period_summaries as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = canonical_period_summaries.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists client_errors_insert on public.client_errors;
create policy client_errors_insert on public.client_errors as permissive for INSERT to authenticated
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((hive_id IS NULL) OR (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = client_errors.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))));
drop policy if exists client_errors_insert_anon on public.client_errors;
create policy client_errors_insert_anon on public.client_errors as permissive for INSERT to anon
  with check (((( SELECT auth.uid() AS uid) IS NULL) AND (hive_id IS NULL) AND (worker_name IS NULL) AND (auth_uid IS NULL) AND (context = ANY (ARRAY['uncaught-error'::text, 'unhandled-rejection'::text])) AND ((page IS NULL) OR (char_length(page) <= 300)) AND ((user_agent IS NULL) OR (char_length(user_agent) <= 300))));
drop policy if exists client_errors_read on public.client_errors;
create policy client_errors_read on public.client_errors as permissive for SELECT to authenticated
  using ((EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = client_errors.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text)))));
drop policy if exists cmms_audit_log_insert on public.cmms_audit_log;
create policy cmms_audit_log_insert on public.cmms_audit_log as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists cmms_audit_log_mark_rolled_back on public.cmms_audit_log;
create policy cmms_audit_log_mark_rolled_back on public.cmms_audit_log as permissive for UPDATE to authenticated
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)) AND (operation = 'file_import'::text)))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)) AND (operation = 'file_import_rolled_back'::text)));
drop policy if exists cmms_audit_log_select on public.cmms_audit_log;
create policy cmms_audit_log_select on public.cmms_audit_log as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists community_posts_delete on public.community_posts;
create policy community_posts_delete on public.community_posts as permissive for DELETE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = community_posts.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text)))))));
drop policy if exists community_posts_insert on public.community_posts;
create policy community_posts_insert on public.community_posts as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (auth_uid IS NULL)) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists community_posts_read on public.community_posts;
create policy community_posts_read on public.community_posts as permissive for SELECT to public
  using ((((public = true) AND (flagged = false)) OR ((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))));
drop policy if exists community_posts_update on public.community_posts;
create policy community_posts_update on public.community_posts as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = community_posts.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text)))))));
drop policy if exists community_reactions_read on public.community_reactions;
create policy community_reactions_read on public.community_reactions as permissive for SELECT to public
  using ((((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM community_posts cp
  WHERE ((cp.id = community_reactions.post_id) AND (cp.public = true))))) OR ((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))));
drop policy if exists community_reactions_write on public.community_reactions;
create policy community_reactions_write on public.community_reactions as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((EXISTS ( SELECT 1
   FROM community_posts cp
  WHERE ((cp.id = community_reactions.post_id) AND (cp.public = true)))) OR (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))));
drop policy if exists community_replies_delete on public.community_replies;
create policy community_replies_delete on public.community_replies as permissive for DELETE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (hive_id IN ( SELECT user_supervisor_hive_ids() AS user_supervisor_hive_ids)))));
drop policy if exists community_replies_insert on public.community_replies;
create policy community_replies_insert on public.community_replies as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists community_replies_modify on public.community_replies;
create policy community_replies_modify on public.community_replies as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (hive_id IN ( SELECT user_supervisor_hive_ids() AS user_supervisor_hive_ids)))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (hive_id IN ( SELECT user_supervisor_hive_ids() AS user_supervisor_hive_ids)))));
drop policy if exists community_replies_read on public.community_replies;
create policy community_replies_read on public.community_replies as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists companion_handoff_hive_all on public.companion_handoff;
create policy companion_handoff_hive_all on public.companion_handoff as permissive for ALL to authenticated
  using ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))))
  with check ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists consult_read on public.consulting_engagements;
create policy consult_read on public.consulting_engagements as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = consulting_engagements.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))));
drop policy if exists conversation_analytics_hive_rw on public.conversation_analytics;
create policy conversation_analytics_hive_rw on public.conversation_analytics as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists dialog_state_insert_own on public.dialog_state;
create policy dialog_state_insert_own on public.dialog_state as permissive for INSERT to public
  with check ((( SELECT auth.uid() AS uid) = worker_id));
drop policy if exists dialog_state_update_own on public.dialog_state;
create policy dialog_state_update_own on public.dialog_state as permissive for UPDATE to public
  using ((( SELECT auth.uid() AS uid) = worker_id));
drop policy if exists dialog_state_worker_access on public.dialog_state;
create policy dialog_state_worker_access on public.dialog_state as permissive for SELECT to public
  using ((( SELECT auth.uid() AS uid) = worker_id));
drop policy if exists drone_read on public.drone_inspections;
create policy drone_read on public.drone_inspections as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists drone_update_supervisor on public.drone_inspections;
create policy drone_update_supervisor on public.drone_inspections as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = drone_inspections.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))
  with check (true);
drop policy if exists engineering_calcs_delete on public.engineering_calcs;
create policy engineering_calcs_delete on public.engineering_calcs as permissive for DELETE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists engineering_calcs_insert on public.engineering_calcs;
create policy engineering_calcs_insert on public.engineering_calcs as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)) AND ((hive_id IS NULL) OR (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))));
drop policy if exists engineering_calcs_read on public.engineering_calcs;
create policy engineering_calcs_read on public.engineering_calcs as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))) OR ((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))))));
drop policy if exists engineering_calcs_update on public.engineering_calcs;
create policy engineering_calcs_update on public.engineering_calcs as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)) AND ((hive_id IS NULL) OR (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))));
drop policy if exists external_sync_hive_rw on public.external_sync;
create policy external_sync_hive_rw on public.external_sync as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists failure_signature_alerts_hive_rw on public.failure_signature_alerts;
create policy failure_signature_alerts_hive_rw on public.failure_signature_alerts as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists fault_knowledge_read on public.fault_knowledge;
create policy fault_knowledge_read on public.fault_knowledge as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))) OR ((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))))));
drop policy if exists gateway_audit_read on public.gateway_audit_log;
create policy gateway_audit_read on public.gateway_audit_log as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (is_platform_admin() OR ((hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = gateway_audit_log.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text))))))));
drop policy if exists hive_adoption_score_read on public.hive_adoption_score;
create policy hive_adoption_score_read on public.hive_adoption_score as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists hive_analytics_cache_hive_rw on public.hive_analytics_cache;
create policy hive_analytics_cache_hive_rw on public.hive_analytics_cache as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists hive_audit_log_insert_member on public.hive_audit_log;
create policy hive_audit_log_insert_member on public.hive_audit_log as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists hive_audit_log_select_supervisor on public.hive_audit_log;
create policy hive_audit_log_select_supervisor on public.hive_audit_log as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_supervisor_hive_ids() AS user_supervisor_hive_ids))));
drop policy if exists hive_benchmarks_hive_rw on public.hive_benchmarks;
create policy hive_benchmarks_hive_rw on public.hive_benchmarks as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists hive_members_delete on public.hive_members;
create policy hive_members_delete on public.hive_members as permissive for DELETE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)) AND (status <> 'kicked'::text)));
drop policy if exists hive_members_insert on public.hive_members;
create policy hive_members_insert on public.hive_members as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)) AND (role = 'supervisor'::text) AND (status = 'active'::text) AND (NOT hive_has_other_members(hive_id))));
drop policy if exists hive_members_read_scoped on public.hive_members;
create policy hive_members_read_scoped on public.hive_members as permissive for SELECT to public
  using (((auth_uid = ( SELECT auth.uid() AS uid)) OR (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists hive_members_update on public.hive_members;
create policy hive_members_update on public.hive_members as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_supervisor_hive_ids() AS user_supervisor_hive_ids))));
drop policy if exists hive_quotas_read on public.hive_quotas;
create policy hive_quotas_read on public.hive_quotas as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = hive_quotas.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists hive_readiness_read on public.hive_readiness;
create policy hive_readiness_read on public.hive_readiness as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists hive_readiness_audit_read on public.hive_readiness_audit;
create policy hive_readiness_audit_read on public.hive_readiness_audit as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists hive_retention_config_read on public.hive_retention_config;
create policy hive_retention_config_read on public.hive_retention_config as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = hive_retention_config.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists hive_retention_config_write on public.hive_retention_config;
create policy hive_retention_config_write on public.hive_retention_config as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = hive_retention_config.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = hive_retention_config.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))));
drop policy if exists hive_route_calls_read on public.hive_route_calls;
create policy hive_route_calls_read on public.hive_route_calls as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = hive_route_calls.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists hive_route_quotas_read on public.hive_route_quotas;
create policy hive_route_quotas_read on public.hive_route_quotas as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = hive_route_quotas.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists hive_service_settings_read on public.hive_service_settings;
create policy hive_service_settings_read on public.hive_service_settings as permissive for SELECT to authenticated
  using ((hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))));
drop policy if exists hive_service_settings_write on public.hive_service_settings;
create policy hive_service_settings_write on public.hive_service_settings as permissive for ALL to authenticated
  using ((hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text)))))
  with check ((hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text)))));
drop policy if exists hives_delete on public.hives;
create policy hives_delete on public.hives as permissive for DELETE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE ((hive_members.auth_uid = ( SELECT auth.uid() AS uid)) AND (hive_members.role = 'supervisor'::text) AND (hive_members.status = 'active'::text))))));
drop policy if exists hives_insert on public.hives;
create policy hives_insert on public.hives as permissive for INSERT to public
  with check ((( SELECT auth.uid() AS uid) IS NOT NULL));
drop policy if exists hives_read_member on public.hives;
create policy hives_read_member on public.hives as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists hives_update on public.hives;
create policy hives_update on public.hives as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE ((hive_members.auth_uid = ( SELECT auth.uid() AS uid)) AND (hive_members.role = 'supervisor'::text) AND (hive_members.status = 'active'::text))))));
drop policy if exists integration_configs_supervisor_all on public.integration_configs;
create policy integration_configs_supervisor_all on public.integration_configs as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = integration_configs.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = integration_configs.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))));
drop policy if exists inventory_items_read on public.inventory_items;
create policy inventory_items_read on public.inventory_items as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR (hive_id = ANY (ARRAY( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))))));
drop policy if exists inventory_items_write on public.inventory_items;
create policy inventory_items_write on public.inventory_items as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR ((auth_uid = ( SELECT auth.uid() AS uid)) AND (hive_id = ANY (ARRAY( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))) OR (hive_id = ANY (ARRAY( SELECT user_supervisor_hive_ids()))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR ((auth_uid = ( SELECT auth.uid() AS uid)) AND (hive_id = ANY (ARRAY( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))) OR (hive_id = ANY (ARRAY( SELECT user_supervisor_hive_ids()))))));
drop policy if exists inventory_transactions_read on public.inventory_transactions;
create policy inventory_transactions_read on public.inventory_transactions as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))) OR ((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))))));
drop policy if exists inventory_transactions_write on public.inventory_transactions;
create policy inventory_transactions_write on public.inventory_transactions as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM inventory_items ii
  WHERE ((ii.id = inventory_transactions.item_id) AND (((ii.hive_id IS NULL) AND (ii.auth_uid = ( SELECT auth.uid() AS uid))) OR (ii.hive_id = ANY (ARRAY( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (auth_uid IS NULL)) AND (EXISTS ( SELECT 1
   FROM inventory_items ii
  WHERE ((ii.id = inventory_transactions.item_id) AND (NOT (ii.hive_id IS DISTINCT FROM inventory_transactions.hive_id)) AND (((ii.hive_id IS NULL) AND (ii.auth_uid = ( SELECT auth.uid() AS uid))) OR (ii.hive_id = ANY (ARRAY( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))))))));
drop policy if exists kb_chunks_hive_access on public.kb_chunks;
create policy kb_chunks_hive_access on public.kb_chunks as permissive for SELECT to public
  using ((EXISTS ( SELECT 1
   FROM (kb_documents kd
     JOIN hive_members hm ON ((hm.hive_id = kd.hive_id)))
  WHERE ((kd.id = kb_chunks.doc_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))));
drop policy if exists kb_documents_hive_access on public.kb_documents;
create policy kb_documents_hive_access on public.kb_documents as permissive for SELECT to public
  using ((EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = kb_documents.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))));
drop policy if exists kgf_read on public.knowledge_graph_facts;
create policy kgf_read on public.knowledge_graph_facts as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists language_prefs_owner_read on public.language_preferences;
create policy language_prefs_owner_read on public.language_preferences as permissive for SELECT to authenticated
  using ((worker_id IN ( SELECT worker_profiles.id
   FROM worker_profiles
  WHERE (worker_profiles.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists language_prefs_owner_rw on public.language_preferences;
create policy language_prefs_owner_rw on public.language_preferences as permissive for ALL to authenticated
  using ((worker_id IN ( SELECT worker_profiles.id
   FROM worker_profiles
  WHERE (worker_profiles.auth_uid = ( SELECT auth.uid() AS uid)))))
  with check ((worker_id IN ( SELECT worker_profiles.id
   FROM worker_profiles
  WHERE (worker_profiles.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists logbook_delete on public.logbook;
create policy logbook_delete on public.logbook as permissive for DELETE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists logbook_insert on public.logbook;
create policy logbook_insert on public.logbook as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))) OR ((hive_id IS NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (auth_uid IS NULL))))));
drop policy if exists logbook_read on public.logbook;
create policy logbook_read on public.logbook as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))) OR ((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))))));
drop policy if exists logbook_update on public.logbook;
create policy logbook_update on public.logbook as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists mkt_disp_insert on public.marketplace_disputes;
create policy mkt_disp_insert on public.marketplace_disputes as permissive for INSERT to authenticated
  with check (((opened_by_auth_uid = ( SELECT auth.uid() AS uid)) AND (opened_by IN ( SELECT auth_worker_names() AS auth_worker_names)) AND ((EXISTS ( SELECT 1
   FROM marketplace_inquiries i
  WHERE ((i.listing_id = marketplace_disputes.listing_id) AND inquiry_is_from_me(i.id)))) OR ((order_id IS NOT NULL) AND order_is_mine(order_id)))));
drop policy if exists mkt_disp_read on public.marketplace_disputes;
create policy mkt_disp_read on public.marketplace_disputes as permissive for SELECT to public
  using (((opened_by_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR ((order_id IS NOT NULL) AND order_is_mine(order_id)) OR is_marketplace_admin()));
drop policy if exists mkt_disp_update on public.marketplace_disputes;
create policy mkt_disp_update on public.marketplace_disputes as permissive for UPDATE to public
  using (((opened_by_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR ((order_id IS NOT NULL) AND order_is_mine(order_id)) OR is_marketplace_admin()))
  with check (((opened_by_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR ((order_id IS NOT NULL) AND order_is_mine(order_id)) OR is_marketplace_admin()));
drop policy if exists mkt_inq_insert on public.marketplace_inquiries;
create policy mkt_inq_insert on public.marketplace_inquiries as permissive for INSERT to public
  with check (((buyer_auth_uid = ( SELECT auth.uid() AS uid)) AND (buyer_name IN ( SELECT auth_worker_names() AS auth_worker_names))));
drop policy if exists mkt_inq_read on public.marketplace_inquiries;
create policy mkt_inq_read on public.marketplace_inquiries as permissive for SELECT to public
  using (((buyer_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR is_marketplace_admin()));
drop policy if exists mkt_inq_update on public.marketplace_inquiries;
create policy mkt_inq_update on public.marketplace_inquiries as permissive for UPDATE to public
  using (((buyer_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR is_marketplace_admin()))
  with check (((buyer_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR is_marketplace_admin()));
drop policy if exists mkt_listings_delete on public.marketplace_listings;
create policy mkt_listings_delete on public.marketplace_listings as permissive for DELETE to public
  using (((auth_uid = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin()));
drop policy if exists mkt_listings_insert on public.marketplace_listings;
create policy mkt_listings_insert on public.marketplace_listings as permissive for INSERT to public
  with check (((auth_uid = ( SELECT auth.uid() AS uid)) AND (seller_name IN ( SELECT auth_worker_names() AS auth_worker_names))));
drop policy if exists mkt_listings_read on public.marketplace_listings;
create policy mkt_listings_read on public.marketplace_listings as permissive for SELECT to public
  using (((status = 'published'::text) OR (auth_uid = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin()));
drop policy if exists mkt_listings_update on public.marketplace_listings;
create policy mkt_listings_update on public.marketplace_listings as permissive for UPDATE to public
  using (((auth_uid = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin()))
  with check (((auth_uid = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin()));
drop policy if exists mkt_orders_insert on public.marketplace_orders;
create policy mkt_orders_insert on public.marketplace_orders as permissive for INSERT to public
  with check (((buyer_auth_uid = ( SELECT auth.uid() AS uid)) AND (buyer_name IN ( SELECT auth_worker_names() AS auth_worker_names))));
drop policy if exists mkt_orders_read on public.marketplace_orders;
create policy mkt_orders_read on public.marketplace_orders as permissive for SELECT to public
  using (((buyer_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR is_marketplace_admin()));
drop policy if exists mkt_orders_update on public.marketplace_orders;
create policy mkt_orders_update on public.marketplace_orders as permissive for UPDATE to public
  using (((buyer_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR is_marketplace_admin()))
  with check (((buyer_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR is_marketplace_admin()));
drop policy if exists mkt_admins_read_self on public.marketplace_platform_admins;
create policy mkt_admins_read_self on public.marketplace_platform_admins as permissive for SELECT to public
  using (((auth_uid IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists mkt_reviews_delete on public.marketplace_reviews;
create policy mkt_reviews_delete on public.marketplace_reviews as permissive for DELETE to public
  using (((reviewer_auth_uid = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin()));
drop policy if exists mkt_reviews_insert on public.marketplace_reviews;
create policy mkt_reviews_insert on public.marketplace_reviews as permissive for INSERT to authenticated
  with check ((is_marketplace_admin() OR ((reviewer_auth_uid = ( SELECT auth.uid() AS uid)) AND (reviewer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) AND (verified_purchase = false) AND (EXISTS ( SELECT 1
   FROM marketplace_inquiries i
  WHERE ((i.listing_id = marketplace_reviews.listing_id) AND inquiry_is_from_me(i.id)))) AND (NOT listing_is_mine(listing_id)))));
drop policy if exists mkt_reviews_update on public.marketplace_reviews;
create policy mkt_reviews_update on public.marketplace_reviews as permissive for UPDATE to public
  using (((reviewer_auth_uid = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin()))
  with check ((is_marketplace_admin() OR ((reviewer_auth_uid = ( SELECT auth.uid() AS uid)) AND (verified_purchase = false))));
drop policy if exists mkt_saved_searches_owner_rw on public.marketplace_saved_searches;
create policy mkt_saved_searches_owner_rw on public.marketplace_saved_searches as permissive for ALL to public
  using ((auth_uid = ( SELECT auth.uid() AS uid)))
  with check (((auth_uid = ( SELECT auth.uid() AS uid)) AND (worker_name IN ( SELECT auth_worker_names() AS auth_worker_names))));
drop policy if exists mkt_sellers_delete on public.marketplace_sellers;
create policy mkt_sellers_delete on public.marketplace_sellers as permissive for DELETE to public
  using (((auth_uid = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin()));
drop policy if exists mkt_sellers_insert on public.marketplace_sellers;
create policy mkt_sellers_insert on public.marketplace_sellers as permissive for INSERT to public
  with check (((auth_uid = ( SELECT auth.uid() AS uid)) AND ((hive_id IS NULL) OR (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))));
drop policy if exists mkt_sellers_read on public.marketplace_sellers;
create policy mkt_sellers_read on public.marketplace_sellers as permissive for SELECT to public
  using ((( SELECT auth.uid() AS uid) IS NOT NULL));
drop policy if exists mkt_sellers_update on public.marketplace_sellers;
create policy mkt_sellers_update on public.marketplace_sellers as permissive for UPDATE to public
  using (((auth_uid = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin()))
  with check ((is_marketplace_admin() OR ((auth_uid = ( SELECT auth.uid() AS uid)) AND ((hive_id IS NULL) OR (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))));
drop policy if exists mkt_watchlist_owner_rw on public.marketplace_watchlist;
create policy mkt_watchlist_owner_rw on public.marketplace_watchlist as permissive for ALL to public
  using ((auth_uid = ( SELECT auth.uid() AS uid)))
  with check (((auth_uid = ( SELECT auth.uid() AS uid)) AND (worker_name IN ( SELECT auth_worker_names() AS auth_worker_names))));
drop policy if exists mentor_relay_queue_hive_all on public.mentor_relay_queue;
create policy mentor_relay_queue_hive_all on public.mentor_relay_queue as permissive for ALL to authenticated
  using ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))))
  with check ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists mfa_enrollments_read on public.mfa_enrollments;
create policy mfa_enrollments_read on public.mfa_enrollments as permissive for SELECT to public
  using ((( SELECT auth.uid() AS uid) = auth_uid));
drop policy if exists offline_snapshot_cache_hive_rw on public.offline_snapshot_cache;
create policy offline_snapshot_cache_hive_rw on public.offline_snapshot_cache as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists parts_records_hive_rw on public.parts_records;
create policy parts_records_hive_rw on public.parts_records as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists parts_staged_reservations_hive_rw on public.parts_staged_reservations;
create policy parts_staged_reservations_hive_rw on public.parts_staged_reservations as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists parts_staging_recommendations_hive_rw on public.parts_staging_recommendations;
create policy parts_staging_recommendations_hive_rw on public.parts_staging_recommendations as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists pdf_jobs_insert on public.pdf_jobs;
create policy pdf_jobs_insert on public.pdf_jobs as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = pdf_jobs.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists pdf_jobs_read on public.pdf_jobs;
create policy pdf_jobs_read on public.pdf_jobs as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = pdf_jobs.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists pf_intervals_parent_hive_guard on public.pf_intervals;
create policy pf_intervals_parent_hive_guard on public.pf_intervals as restrictive for ALL to public
  using (true)
  with check (((( SELECT auth.uid() AS uid) IS NULL) OR (asset_id IS NULL) OR (EXISTS ( SELECT 1
   FROM asset_nodes n
  WHERE ((n.id = pf_intervals.asset_id) AND (NOT (n.hive_id IS DISTINCT FROM pf_intervals.hive_id)))))));
drop policy if exists pf_intervals_read on public.pf_intervals;
create policy pf_intervals_read on public.pf_intervals as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists pm_assets_delete_guard on public.pm_assets;
create policy pm_assets_delete_guard on public.pm_assets as restrictive for DELETE to public
  using ((((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR ((hive_id IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = pm_assets.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text)))))) OR (( SELECT auth.uid() AS uid) IS NULL)));
drop policy if exists pm_assets_insert_guard on public.pm_assets;
create policy pm_assets_insert_guard on public.pm_assets as restrictive for INSERT to public
  with check ((((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR ((hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = pm_assets.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text))))) OR (( SELECT auth.uid() AS uid) IS NULL)));
drop policy if exists pm_assets_read on public.pm_assets;
create policy pm_assets_read on public.pm_assets as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id = ANY (ARRAY( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))) OR ((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))))));
drop policy if exists pm_assets_update_guard on public.pm_assets;
create policy pm_assets_update_guard on public.pm_assets as restrictive for UPDATE to public
  using ((((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR ((hive_id IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = pm_assets.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text)))))) OR (( SELECT auth.uid() AS uid) IS NULL)));
drop policy if exists pm_assets_write on public.pm_assets;
create policy pm_assets_write on public.pm_assets as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR (hive_id = ANY (ARRAY( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR (hive_id = ANY (ARRAY( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))))));
drop policy if exists pm_completions_read on public.pm_completions;
create policy pm_completions_read on public.pm_completions as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))) OR ((hive_id IS NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))))));
drop policy if exists pm_completions_write on public.pm_completions;
create policy pm_completions_write on public.pm_completions as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)) AND (((hive_id IS NULL) AND (EXISTS ( SELECT 1
   FROM pm_assets pa
  WHERE ((pa.id = pm_completions.asset_id) AND (pa.hive_id IS NULL) AND (pa.auth_uid = ( SELECT auth.uid() AS uid)))))) OR ((hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))) AND (EXISTS ( SELECT 1
   FROM pm_assets pa
  WHERE ((pa.id = pm_completions.asset_id) AND (NOT (pa.hive_id IS DISTINCT FROM pm_completions.hive_id)))))))));
drop policy if exists pm_knowledge_read on public.pm_knowledge;
create policy pm_knowledge_read on public.pm_knowledge as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists pm_scope_items_read on public.pm_scope_items;
create policy pm_scope_items_read on public.pm_scope_items as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((asset_id IN ( SELECT pa.id
   FROM pm_assets pa
  WHERE ((pa.hive_id IS NULL) AND (pa.auth_uid = ( SELECT auth.uid() AS uid))))) OR (asset_id IN ( SELECT pa.id
   FROM (pm_assets pa
     JOIN hive_members hm ON ((pa.hive_id = hm.hive_id)))
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))));
drop policy if exists pm_scope_items_write on public.pm_scope_items;
create policy pm_scope_items_write on public.pm_scope_items as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM pm_assets pa
  WHERE ((pa.id = pm_scope_items.asset_id) AND (((pa.hive_id IS NULL) AND (pa.auth_uid = ( SELECT auth.uid() AS uid))) OR (pa.hive_id = ANY (ARRAY( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM pm_assets pa
  WHERE ((pa.id = pm_scope_items.asset_id) AND (NOT (pa.hive_id IS DISTINCT FROM pm_scope_items.hive_id)) AND (((pa.hive_id IS NULL) AND (pa.auth_uid = ( SELECT auth.uid() AS uid))) OR (pa.hive_id = ANY (ARRAY( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))))))))));
drop policy if exists project_change_orders_hive_rw on public.project_change_orders;
create policy project_change_orders_hive_rw on public.project_change_orders as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists project_change_orders_parent_hive_guard on public.project_change_orders;
create policy project_change_orders_parent_hive_guard on public.project_change_orders as restrictive for ALL to public
  using (true)
  with check (((( SELECT auth.uid() AS uid) IS NULL) OR (project_id IS NULL) OR (EXISTS ( SELECT 1
   FROM projects p
  WHERE ((p.id = project_change_orders.project_id) AND (NOT (p.hive_id IS DISTINCT FROM project_change_orders.hive_id)))))));
drop policy if exists project_items_hive_rw on public.project_items;
create policy project_items_hive_rw on public.project_items as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists project_items_parent_hive_guard on public.project_items;
create policy project_items_parent_hive_guard on public.project_items as restrictive for ALL to public
  using (true)
  with check (((( SELECT auth.uid() AS uid) IS NULL) OR (project_id IS NULL) OR (EXISTS ( SELECT 1
   FROM projects p
  WHERE ((p.id = project_items.project_id) AND (NOT (p.hive_id IS DISTINCT FROM project_items.hive_id)))))));
drop policy if exists project_knowledge_hive_rw on public.project_knowledge;
create policy project_knowledge_hive_rw on public.project_knowledge as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists project_knowledge_parent_hive_guard on public.project_knowledge;
create policy project_knowledge_parent_hive_guard on public.project_knowledge as restrictive for ALL to public
  using (true)
  with check (((( SELECT auth.uid() AS uid) IS NULL) OR (project_id IS NULL) OR (EXISTS ( SELECT 1
   FROM projects p
  WHERE ((p.id = project_knowledge.project_id) AND (NOT (p.hive_id IS DISTINCT FROM project_knowledge.hive_id)))))));
drop policy if exists project_links_hive_rw on public.project_links;
create policy project_links_hive_rw on public.project_links as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists project_links_parent_hive_guard on public.project_links;
create policy project_links_parent_hive_guard on public.project_links as restrictive for ALL to public
  using (true)
  with check (((( SELECT auth.uid() AS uid) IS NULL) OR (project_id IS NULL) OR (EXISTS ( SELECT 1
   FROM projects p
  WHERE ((p.id = project_links.project_id) AND (NOT (p.hive_id IS DISTINCT FROM project_links.hive_id)))))));
drop policy if exists project_progress_logs_hive_rw on public.project_progress_logs;
create policy project_progress_logs_hive_rw on public.project_progress_logs as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists project_progress_logs_parent_hive_guard on public.project_progress_logs;
create policy project_progress_logs_parent_hive_guard on public.project_progress_logs as restrictive for ALL to public
  using (true)
  with check (((( SELECT auth.uid() AS uid) IS NULL) OR (project_id IS NULL) OR (EXISTS ( SELECT 1
   FROM projects p
  WHERE ((p.id = project_progress_logs.project_id) AND (NOT (p.hive_id IS DISTINCT FROM project_progress_logs.hive_id)))))));
drop policy if exists project_roles_supervisor_all on public.project_roles;
create policy project_roles_supervisor_all on public.project_roles as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = project_roles.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = project_roles.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))));
drop policy if exists projects_hive_rw on public.projects;
create policy projects_hive_rw on public.projects as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists push_subscriptions_own on public.push_subscriptions;
create policy push_subscriptions_own on public.push_subscriptions as permissive for ALL to authenticated
  using ((auth_uid = ( SELECT auth.uid() AS uid)))
  with check ((auth_uid = ( SELECT auth.uid() AS uid)));
drop policy if exists rcm_fmea_modes_parent_hive_guard on public.rcm_fmea_modes;
create policy rcm_fmea_modes_parent_hive_guard on public.rcm_fmea_modes as restrictive for ALL to public
  using (true)
  with check (((( SELECT auth.uid() AS uid) IS NULL) OR (asset_id IS NULL) OR (EXISTS ( SELECT 1
   FROM asset_nodes n
  WHERE ((n.id = rcm_fmea_modes.asset_id) AND (NOT (n.hive_id IS DISTINCT FROM rcm_fmea_modes.hive_id)))))));
drop policy if exists rcm_fmea_modes_read on public.rcm_fmea_modes;
create policy rcm_fmea_modes_read on public.rcm_fmea_modes as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists rcm_fmea_modes_write on public.rcm_fmea_modes;
create policy rcm_fmea_modes_write on public.rcm_fmea_modes as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists rcm_strategies_parent_hive_guard on public.rcm_strategies;
create policy rcm_strategies_parent_hive_guard on public.rcm_strategies as restrictive for ALL to public
  using (true)
  with check (((( SELECT auth.uid() AS uid) IS NULL) OR (fmea_mode_id IS NULL) OR (EXISTS ( SELECT 1
   FROM rcm_fmea_modes m
  WHERE ((m.id = rcm_strategies.fmea_mode_id) AND (NOT (m.hive_id IS DISTINCT FROM rcm_strategies.hive_id)))))));
drop policy if exists rcm_strategies_read on public.rcm_strategies;
create policy rcm_strategies_read on public.rcm_strategies as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists rcm_strategies_write on public.rcm_strategies;
create policy rcm_strategies_write on public.rcm_strategies as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists report_contacts_read on public.report_contacts;
create policy report_contacts_read on public.report_contacts as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE ((hive_members.auth_uid = ( SELECT auth.uid() AS uid)) AND (hive_members.status = 'active'::text))))));
drop policy if exists report_contacts_write on public.report_contacts;
create policy report_contacts_write on public.report_contacts as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists resume_documents_delete on public.resume_documents;
create policy resume_documents_delete on public.resume_documents as permissive for DELETE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists resume_documents_insert on public.resume_documents;
create policy resume_documents_insert on public.resume_documents as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid) AND ((hive_id IS NULL) OR (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))));
drop policy if exists resume_documents_read on public.resume_documents;
create policy resume_documents_read on public.resume_documents as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists resume_documents_update on public.resume_documents;
create policy resume_documents_update on public.resume_documents as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid) AND ((hive_id IS NULL) OR (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))));
drop policy if exists resume_versions_delete on public.resume_versions;
create policy resume_versions_delete on public.resume_versions as permissive for DELETE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists resume_versions_insert on public.resume_versions;
create policy resume_versions_insert on public.resume_versions as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists resume_versions_read on public.resume_versions;
create policy resume_versions_read on public.resume_versions as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists schedule_items_read on public.schedule_items;
create policy schedule_items_read on public.schedule_items as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists schedule_items_write on public.schedule_items;
create policy schedule_items_write on public.schedule_items as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists sensor_readings_read on public.sensor_readings;
create policy sensor_readings_read on public.sensor_readings as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists sensor_topic_map_read on public.sensor_topic_map;
create policy sensor_topic_map_read on public.sensor_topic_map as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists sensor_topic_map_write_supervisor on public.sensor_topic_map;
create policy sensor_topic_map_write_supervisor on public.sensor_topic_map as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = sensor_topic_map.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = sensor_topic_map.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))));
drop policy if exists service_credit_ledger_own_read on public.service_credit_ledger;
create policy service_credit_ledger_own_read on public.service_credit_ledger as permissive for SELECT to authenticated
  using ((((account_type = 'consumer'::text) AND (account_id = ( SELECT auth.uid() AS uid))) OR ((account_type = 'provider'::text) AND (account_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids))) OR is_marketplace_admin()));
drop policy if exists service_credit_topups_intake on public.service_credit_topups;
create policy service_credit_topups_intake on public.service_credit_topups as permissive for INSERT to authenticated
  with check ((payer_auth_uid = ( SELECT auth.uid() AS uid)));
drop policy if exists service_credit_topups_own on public.service_credit_topups;
create policy service_credit_topups_own on public.service_credit_topups as permissive for SELECT to authenticated
  using (((payer_auth_uid = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin()));
drop policy if exists service_offers_party_read on public.service_offers;
create policy service_offers_party_read on public.service_offers as permissive for SELECT to authenticated
  using (((provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids)) OR (request_id IN ( SELECT r.id
   FROM service_requests r
  WHERE (r.client_auth_uid = ( SELECT auth.uid() AS uid))))));
drop policy if exists service_offers_party_update on public.service_offers;
create policy service_offers_party_update on public.service_offers as permissive for UPDATE to authenticated
  using (((provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids)) OR (request_id IN ( SELECT r.id
   FROM service_requests r
  WHERE (r.client_auth_uid = ( SELECT auth.uid() AS uid))))));
drop policy if exists service_payments_intake on public.service_payments;
create policy service_payments_intake on public.service_payments as permissive for INSERT to public
  with check (((confirmed_by = ( SELECT auth.uid() AS uid)) AND (EXISTS ( SELECT 1
   FROM service_requests r
  WHERE ((r.id = service_payments.request_id) AND (r.client_auth_uid = ( SELECT auth.uid() AS uid)))))));
drop policy if exists service_payments_read on public.service_payments;
create policy service_payments_read on public.service_payments as permissive for SELECT to public
  using (((confirmed_by = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin() OR (EXISTS ( SELECT 1
   FROM service_requests r
  WHERE ((r.id = service_payments.request_id) AND ((r.client_auth_uid = ( SELECT auth.uid() AS uid)) OR (r.matched_provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids))))))));
drop policy if exists service_providers_self_insert on public.service_providers;
create policy service_providers_self_insert on public.service_providers as permissive for INSERT to authenticated
  with check ((((provider_type = 'freelancer'::text) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR ((provider_type = 'hive'::text) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text)))))));
drop policy if exists service_providers_self_update on public.service_providers;
create policy service_providers_self_update on public.service_providers as permissive for UPDATE to authenticated
  using (((auth_uid = ( SELECT auth.uid() AS uid)) OR ((provider_type = 'hive'::text) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text)))))));
drop policy if exists service_requests_client_insert on public.service_requests;
create policy service_requests_client_insert on public.service_requests as permissive for INSERT to authenticated
  with check ((client_auth_uid = ( SELECT auth.uid() AS uid)));
drop policy if exists service_requests_party_read on public.service_requests;
create policy service_requests_party_read on public.service_requests as permissive for SELECT to authenticated
  using (((client_auth_uid = ( SELECT auth.uid() AS uid)) OR ((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))) OR (matched_provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids))));
drop policy if exists service_requests_party_update on public.service_requests;
create policy service_requests_party_update on public.service_requests as permissive for UPDATE to authenticated
  using (((client_auth_uid = ( SELECT auth.uid() AS uid)) OR (matched_provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids))));
drop policy if exists service_voucher_redemptions_own_read on public.service_voucher_redemptions;
create policy service_voucher_redemptions_own_read on public.service_voucher_redemptions as permissive for SELECT to authenticated
  using (((consumer_auth_uid = ( SELECT auth.uid() AS uid)) OR is_marketplace_admin()));
drop policy if exists shared_voice_notes_hive_all on public.shared_voice_notes;
create policy shared_voice_notes_hive_all on public.shared_voice_notes as permissive for ALL to authenticated
  using ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))))
  with check ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists shift_plans_read on public.shift_plans;
create policy shift_plans_read on public.shift_plans as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists shift_plans_supervisor_write on public.shift_plans;
create policy shift_plans_supervisor_write on public.shift_plans as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = shift_plans.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))));
drop policy if exists skill_badges_read on public.skill_badges;
create policy skill_badges_read on public.skill_badges as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists skill_exam_attempts_read on public.skill_exam_attempts;
create policy skill_exam_attempts_read on public.skill_exam_attempts as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists skill_knowledge_read on public.skill_knowledge;
create policy skill_knowledge_read on public.skill_knowledge as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists skill_profiles_read on public.skill_profiles;
create policy skill_profiles_read on public.skill_profiles as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists skill_profiles_write on public.skill_profiles;
create policy skill_profiles_write on public.skill_profiles as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists sso_configs_read on public.sso_configs;
create policy sso_configs_read on public.sso_configs as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = sso_configs.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.role = 'supervisor'::text) AND (hm.status = 'active'::text))))));
drop policy if exists tts_quality_log_hive_rw on public.tts_quality_log;
create policy tts_quality_log_hive_rw on public.tts_quality_log as permissive for ALL to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))));
drop policy if exists ue_read on public.unified_events;
create policy ue_read on public.unified_events as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM hive_members hm
  WHERE ((hm.hive_id = unified_events.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists voice_journal_delete on public.voice_journal_entries;
create policy voice_journal_delete on public.voice_journal_entries as permissive for DELETE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists voice_journal_insert on public.voice_journal_entries;
create policy voice_journal_insert on public.voice_journal_entries as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists voice_journal_read on public.voice_journal_entries;
create policy voice_journal_read on public.voice_journal_entries as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists voice_journal_update on public.voice_journal_entries;
create policy voice_journal_update on public.voice_journal_entries as permissive for UPDATE to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)))
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid)));
drop policy if exists voice_queue_own_rows on public.voice_response_queue;
create policy voice_queue_own_rows on public.voice_response_queue as permissive for SELECT to authenticated
  using ((worker_id = ( SELECT auth.uid() AS uid)));
drop policy if exists weibull_fits_parent_hive_guard on public.weibull_fits;
create policy weibull_fits_parent_hive_guard on public.weibull_fits as restrictive for ALL to public
  using (true)
  with check (((( SELECT auth.uid() AS uid) IS NULL) OR (asset_id IS NULL) OR (EXISTS ( SELECT 1
   FROM asset_nodes n
  WHERE ((n.id = weibull_fits.asset_id) AND (NOT (n.hive_id IS DISTINCT FROM weibull_fits.hive_id)))))));
drop policy if exists weibull_fits_read on public.weibull_fits;
create policy weibull_fits_read on public.weibull_fits as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id
   FROM hive_members hm
  WHERE ((hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text))))));
drop policy if exists wh_feature_flags_hive_select on public.wh_feature_flags;
create policy wh_feature_flags_hive_select on public.wh_feature_flags as permissive for SELECT to authenticated
  using ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists wh_voice_presence_hive_all on public.wh_voice_presence;
create policy wh_voice_presence_hive_all on public.wh_voice_presence as permissive for ALL to authenticated
  using ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))))
  with check ((hive_id IN ( SELECT hive_members.hive_id
   FROM hive_members
  WHERE (hive_members.auth_uid = ( SELECT auth.uid() AS uid)))));
drop policy if exists worker_achievements_read on public.worker_achievements;
create policy worker_achievements_read on public.worker_achievements as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((auth_uid = ( SELECT auth.uid() AS uid)) OR (worker_name IN ( SELECT user_hive_worker_names() AS user_hive_worker_names)))));
drop policy if exists "profiles insert own" on public.worker_profiles;
create policy "profiles insert own" on public.worker_profiles as permissive for INSERT to public
  with check (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
drop policy if exists "profiles update own" on public.worker_profiles;
create policy "profiles update own" on public.worker_profiles as permissive for UPDATE to public
  using ((( SELECT auth.uid() AS uid) = auth_uid));
drop policy if exists profiles_read_own on public.worker_profiles;
create policy profiles_read_own on public.worker_profiles as permissive for SELECT to public
  using (((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid))));
