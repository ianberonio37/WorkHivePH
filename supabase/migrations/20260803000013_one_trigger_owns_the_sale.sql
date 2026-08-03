-- A sale moved no credits, because two triggers each did half the job in the wrong order.
--
-- `release_reservation_on_delist` marked the reservation `released_to_buyer`; `grant_listing_reward` then
-- read that state and wrote the ledger legs. Both are AFTER UPDATE OF status on marketplace_listings, and
-- **Postgres fires triggers in ALPHABETICAL ORDER BY NAME**:
--
--     trg_grant_listing_reward   <-- 'g' sorts first, so it ran FIRST
--     trg_release_reservation    <-- 'r', so the state it was waiting for arrived AFTER it had given up
--
-- So the reward trigger found no released reservation, returned early, and the sale completed with the
-- credits still sitting in the seller's reserved balance: the buyer got nothing, the seller lost nothing,
-- and NOTHING ERRORED. A silent no-op is the worst possible outcome here, because the listing shows as
-- sold and the reward simply never exists.
--
-- Measured, not guessed: an end-to-end sale reserved PHP200 on publish and then moved PHP0 to the buyer.
--
-- The fix is not to rename a trigger into a luckier alphabetical position - that encodes a dependency in
-- a string, where the next person to rename it breaks the sale again and finds out from a customer. ONE
-- trigger now owns the whole sold path: it reads the HELD reservation, writes both ledger legs, and marks
-- the reservation released, in that order, in one place. The other trigger keeps only what is genuinely
-- its own: returning the reservation when a listing is delisted or drafted.

-- release_reservation_on_delist loses the 'sold' branch entirely; it now only RETURNS reservations.
create or replace function public.release_reservation_on_delist()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
begin
  if new.status = old.status then return new; end if;
  -- Only the un-selling paths. 'sold' belongs to grant_listing_reward(), which needs the reservation
  -- still HELD when it runs and must not race another trigger for it.
  if new.status in ('removed','draft') then
    update public.credit_reservations
       set state = 'returned', released_at = now()
     where listing_id = new.id and state = 'held';
  end if;
  return new;
end $function$;

-- grant_listing_reward owns the sale end to end.
create or replace function public.grant_listing_reward()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_amt numeric; v_buyer uuid; v_seller uuid;
begin
  if new.status <> 'sold' or old.status = 'sold' then return new; end if;

  -- reads HELD, not released_to_buyer: this function is what releases it
  select amount into v_amt from public.credit_reservations
   where listing_id = new.id and state = 'held' order by created_at desc limit 1;
  if v_amt is null or v_amt <= 0 then return new; end if;

  select auth_uid into v_seller from public.marketplace_sellers where worker_name = new.seller_name limit 1;
  select i.buyer_auth_uid into v_buyer
    from public.marketplace_inquiries i where i.id = new.sold_to_inquiry_id;

  -- A reward with nowhere to go must never become a silent deduction: with no resolvable buyer the
  -- credits go back to the seller rather than vanishing.
  if v_buyer is null or v_seller is null then
    update public.credit_reservations set state = 'returned', released_at = now()
     where listing_id = new.id and state = 'held';
    return new;
  end if;

  -- A vetted platform act: SECURITY DEFINER changes the ROLE but not the JWT, so auth.uid() here is
  -- whoever marked the listing sold, and the non-transferable guard would otherwise refuse both legs.
  perform set_config('workhive.service_system_write', 'on', true);
  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
  values ('consumer', v_seller, 'reward_fund', -v_amt, 'listing', new.id,
          'funded the buyer reward: ' || left(coalesce(new.title,''), 40));
  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
  values ('consumer', v_buyer,  'reward_earn',  v_amt, 'listing', new.id,
          'reward for buying: ' || left(coalesce(new.title,''), 40));
  perform set_config('workhive.service_system_write', 'off', true);

  update public.credit_reservations set state = 'released_to_buyer', released_at = now()
   where listing_id = new.id and state = 'held';
  return new;
end $function$;

comment on function public.grant_listing_reward() is
  'Owns the SOLD path end to end: reads the HELD reservation, writes both ledger legs, then marks it '
  'released. It previously depended on another AFTER-trigger having run first, and Postgres fires '
  'triggers alphabetically - trg_grant_listing_reward sorted before trg_release_reservation, so the '
  'state it waited for arrived too late and every sale silently moved zero credits.';
