-- SL LB1 walk (2026-10-21): a seller's public profile showed a signed-in visitor the visitor's OWN slice of the seller's
-- inquiries as if it were the seller's record. "Inquiries Replied" and "Avg Reply" were computed from
-- v_marketplace_inquiries_truth, and RLS lets a person read only the conversations they are party to. Measured on the
-- local stack: a signed-in visitor opening Bryan Garcia's profile read 0 rows and was told "0 replied - None yet" about a
-- seller with 2 replies and a 172-hour average, while a signed-out stranger, reading the public seller view, was told
-- 172h. The Quick Reply badge needs 5 replies under 4 hours, so no visitor but the seller's own trading partners could
-- ever see it.
--
-- Both figures are facts about the SELLER - the same class as response_rate / response_time_h, which
-- get_marketplace_seller_public already gives every visitor and the trigger from 20260724000006 maintains from the whole
-- inquiry record. This returns the reply count beside the average, computed exactly as that trigger computes it (every
-- replied inquiry, hours to reply, one decimal), and nothing else: two aggregates - no row, no buyer, no message. Every
-- visitor now reads the same two numbers, and the profile no longer caps a read at 50 to average a slice of it.

create function public.marketplace_seller_reply_stats(p_worker_name text)
returns table(replied_count integer, avg_reply_h numeric)
language sql
stable
security definer
set search_path = ''
as $function$
  select count(*) filter (where i.replied_at is not null)::integer,
         round((avg(extract(epoch from (i.replied_at - i.created_at)) / 3600.0)
                filter (where i.replied_at is not null))::numeric, 1)
  from public.marketplace_inquiries i
  where i.seller_name = p_worker_name;
$function$;

comment on function public.marketplace_seller_reply_stats(text) is
  'The public seller profile''s reply figures: how many inquiries the seller has replied to and the average hours to reply, '
  'over the whole inquiry record (the formula marketplace_sellers.response_time_h uses). Aggregates only - no row, buyer '
  'or message - so every visitor reads the same numbers. SL LB1, 2026-10-21.';

-- a public seller fact, like get_marketplace_seller_public: anon keeps EXECUTE, deliberately
revoke execute on function public.marketplace_seller_reply_stats(text) from public;
grant execute on function public.marketplace_seller_reply_stats(text) to anon, authenticated, service_role;

notify pgrst, 'reload schema';
