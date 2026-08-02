-- The seller's funding leg is not the buyer's spend, and conflating them made two guards fight.
--
-- `grant_listing_reward` writes two ledger rows against one listing: the seller's credits leave, the
-- buyer's arrive. Both were typed `reward_spend` / `reward_earn` with the same ref_id — so
-- `guard_reward_exclusive`, which refuses a job carrying both, refused the pair outright. Every listing
-- sale would have failed.
--
-- The rule Ian described governs the BUYER's choice: on a given purchase they either take the reward or
-- spend their own credits, never both. The seller's side is bookkeeping — the credits they had reserved
-- moving out. Giving it its own type keeps the exclusivity rule about the thing it is actually about.
--
--   reward_fund   seller's reserved credits leaving, when a listing sells   (negative, seller)
--   reward_earn   buyer receives the reward                                 (positive, buyer)
--   reward_spend  buyer pays part of a purchase in credits                  (negative, buyer)
--
-- Only earn and spend are mutually exclusive. Caught by reading the interaction back rather than by a
-- failing sale, which is the cheaper place to find it.

alter table public.service_credit_ledger
  drop constraint if exists service_credit_ledger_entry_type_check;
alter table public.service_credit_ledger
  add constraint service_credit_ledger_entry_type_check
  check (entry_type in ('topup','commission','voucher_grant','voucher_reimburse','adjustment','cashback',
                        'reward_earn','reward_spend','reward_fund','starter_grant','holding_fee'));

create or replace function public.grant_listing_reward()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_amt numeric; v_buyer uuid; v_seller uuid;
begin
  if new.status <> 'sold' or old.status = 'sold' then return new; end if;

  select amount into v_amt from public.credit_reservations
   where listing_id = new.id and state = 'released_to_buyer' order by created_at desc limit 1;
  if v_amt is null or v_amt <= 0 then return new; end if;

  select auth_uid into v_seller from public.marketplace_sellers where worker_name = new.seller_name limit 1;
  select i.buyer_auth_uid into v_buyer
    from public.marketplace_inquiries i where i.id = new.sold_to_inquiry_id;

  -- A reward with nowhere to go must never become a silent deduction: if no buyer account can be
  -- resolved, the reservation is RETURNED to the seller rather than disappearing.
  if v_buyer is null or v_seller is null then
    update public.credit_reservations set state = 'returned'
     where listing_id = new.id and state = 'released_to_buyer';
    return new;
  end if;

  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
  values ('consumer', v_seller, 'reward_fund', -v_amt, 'listing', new.id,
          'funded the buyer reward: ' || left(coalesce(new.title,''), 40));
  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
  values ('consumer', v_buyer,  'reward_earn',  v_amt, 'listing', new.id,
          'reward for buying: ' || left(coalesce(new.title,''), 40));
  return new;
end $function$;

comment on function public.grant_listing_reward() is
  'On a sold listing, moves the seller''s reserved credits to the buyer: reward_fund (seller, negative) '
  'and reward_earn (buyer, positive). reward_fund is deliberately NOT reward_spend, so the earn/spend '
  'exclusivity rule stays about the BUYER''s choice rather than blocking every sale.';
