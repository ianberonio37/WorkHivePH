-- Critic deepwalk T11 S4 (2026-09-02): RESERVED STOCK WAS NOT ENFORCED. The Use dialog correctly
-- computed 'Available: 0 pcs (1 on hand - 1 staged for a predicted failure)' yet Confirm Use
-- COMMITTED anyway, silently consuming the unit staged for a predicted asset failure (the toast
-- then celebrated 'now OUT OF STOCK'). The display had the number; the WRITE PATH had no guard —
-- the fix-every-path-that-mutates lesson. This mirrors guard_listing_requires_reservation (the
-- marketplace credit-hold): a DB-level BEFORE INSERT guard on consuming transactions that refuses
-- when the write would push on-hand below the actively-staged total, with a legible refusal
-- (errcode check_violation so whWriteError surfaces the sentence verbatim) naming the asset the
-- part is staged for and the action that CAN work. Vetted service/seeder writes bypass, as
-- everywhere. NOTE the trigger name sorts before trg_inventory_sync_balance so it reads
-- qty_on_hand PRE-update.
create or replace function public.guard_staged_stock()
returns trigger
language plpgsql
security definer
set search_path = public
as $function$
declare v_on_hand numeric; v_reserved numeric; v_free numeric; v_assets text;
begin
  if auth.uid() is null or current_setting('workhive.service_system_write', true) = 'on' then
    return new;   -- seeders / vetted system writes are trusted, as everywhere in this schema
  end if;
  if coalesce(new.qty_change, 0) >= 0 then
    return new;   -- restocks/adjust-ups can never eat staged stock
  end if;

  select qty_on_hand into v_on_hand from public.inventory_items where id = new.item_id;
  select coalesce(sum(qty_reserved), 0),
         string_agg(distinct asset_name, ', ')
    into v_reserved, v_assets
    from public.parts_staged_reservations
   where item_id = new.item_id and consumed_at is null and released_at is null;

  if v_reserved <= 0 then return new; end if;

  v_free := coalesce(v_on_hand, 0) + new.qty_change - v_reserved;  -- post-write on-hand minus staged
  if v_free < 0 then
    raise exception 'Only % free: % on hand and % staged for a predicted failure on %. Taking this would consume the staged part, so nothing was saved.',
      greatest(0, coalesce(v_on_hand,0) - v_reserved), coalesce(v_on_hand,0), v_reserved, coalesce(v_assets, 'an asset')
      using errcode = 'check_violation',
            hint = 'Restock first, or ask a supervisor to release the staging if that repair is no longer planned.';
  end if;
  return new;
end $function$;

drop trigger if exists trg_guard_staged_stock on public.inventory_transactions;
create trigger trg_guard_staged_stock
  before insert on public.inventory_transactions
  for each row execute function public.guard_staged_stock();
