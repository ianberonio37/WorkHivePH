-- Critic deepwalk T34 (2026-09-02): the reservation guard's refusal said "you have % available" —
-- correct for the SELLER pressing publish, wrong-audience for the ADMIN pressing Approve on the
-- moderation queue, who read "you have 0 available" about the SELLER's wallet (walked live: Pablo
-- approving Bryan's draft). The sentence is server-authored (P0001/check_violation raise) and is
-- deliberately surfaced verbatim by whWriteError's deliberate-refusal rule, so the fix is at the
-- source: NAME the seller. "Publishing needs P250 held; Bryan Garcia has P0 available" reads
-- correctly for the seller, the admin, and a log line. Message-only change: the guard's logic,
-- errcode and hint are byte-identical to 20260803000007.
create or replace function public.guard_listing_requires_reservation()
returns trigger
language plpgsql
security definer
set search_path = public
as $function$
declare v_need numeric; v_avail numeric; v_held numeric;
begin
  -- backend/system writes (seeders, sweeps) are vetted, as everywhere else in this schema
  if auth.uid() is null or current_setting('workhive.service_system_write', true) = 'on' then
    return new;
  end if;

  -- only on the transition INTO published; an already-published row being edited keeps its reservation
  if new.status <> 'published' or (TG_OP = 'UPDATE' and old.status = 'published') then
    return new;
  end if;

  v_need := public.listing_reservation_amount(new.hive_id, new.price);
  if v_need <= 0 then return new; end if;

  select available into v_avail from public.seller_credit_balance(new.seller_name);
  select coalesce(sum(amount),0) into v_held
    from public.credit_reservations where listing_id = new.id and state = 'held';

  if v_held >= v_need then return new; end if;      -- already reserved (e.g. a re-publish)

  if coalesce(v_avail,0) < (v_need - v_held) then
    raise exception 'Publishing needs % credits held (10%% of the price); % has % available. '
                    'The credits are not a fee - they come back in full if it does not sell, and go to '
                    'the buyer if it does.',
                    to_char(v_need,'FM999G999G990'), new.seller_name, to_char(coalesce(v_avail,0),'FM999G999G990')
      using errcode = 'check_violation',
            hint = 'Top up credits, or delist something to free the credits it is holding.';
  end if;

  insert into public.credit_reservations (listing_id, seller_name, hive_id, amount)
  values (new.id, new.seller_name, new.hive_id, v_need - v_held);
  return new;
end $function$;
