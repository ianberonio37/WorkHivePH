-- A dispute can only be opened by someone who was party to the listing (EX-HP H6, 2026-09-07).
--
-- Measured as a plain worker through PostgREST on his own token: with ZERO inquiries on a listing he
-- had never touched, he opened a dispute against its seller and PostgREST answered 201. The insert
-- policy checked only that opened_by was his own name - that he was who he said he was - and nothing
-- about whether he had any standing to dispute. That is the shape that lets anyone with an account
-- attack any seller's reputation, and it is exactly what the hostile-persona wave exists to find.
--
-- A party to a listing is someone who INQUIRED on it (this platform's marketplace moves money through
-- inquiries, not carts) or who owns the ORDER the dispute names. Both are checked against the
-- caller's own names via auth_worker_names(), the same binding every other marketplace policy uses.
drop policy if exists mkt_disp_insert on public.marketplace_disputes;
create policy mkt_disp_insert on public.marketplace_disputes
  for insert to authenticated
  with check (
    opened_by in (select auth_worker_names())
    and (
      exists (select 1 from public.marketplace_inquiries i
               where i.listing_id = marketplace_disputes.listing_id
                 and i.buyer_name in (select auth_worker_names()))
      or (marketplace_disputes.order_id is not null
          and exists (select 1 from public.marketplace_orders o
                       where o.id = marketplace_disputes.order_id
                         and (o.buyer_name in (select auth_worker_names())
                              or o.seller_name in (select auth_worker_names()))))
    )
  );
