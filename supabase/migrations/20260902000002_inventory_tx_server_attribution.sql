-- Critic deepwalk T11 (2026-09-02): AUDIT MISATTRIBUTION — inventory_transactions.worker_name was
-- CLIENT-SUPPLIED and wrong. Reproduced twice live: both of Bryan Garcia's "Use" writes carried
-- auth_uid=bryangarcia (JWT, correct) but worker_name='Leandro Marquez' (a stale client variable) —
-- so any part-take can bear anyone's name, and audit surfaces display worker_name. The platform's
-- own discipline (the XP and exam paths) is JWT-not-body: identity comes from the session, never
-- the payload. This trigger applies it here: on INSERT by a real user session, worker_name and
-- auth_uid are DERIVED from auth.uid() + hive_members for the row's hive, overriding whatever the
-- client sent. Seeder/system writes (no auth.uid(), or the vetted service flag) pass untouched —
-- the same bypass idiom as guard_listing_requires_reservation.
create or replace function public.derive_inventory_tx_attribution()
returns trigger
language plpgsql
security definer
set search_path = public
as $function$
declare v_name text;
begin
  if auth.uid() is null or current_setting('workhive.service_system_write', true) = 'on' then
    return new;   -- seeders / vetted system writes keep their stated attribution
  end if;

  select hm.worker_name into v_name
    from public.hive_members hm
   where hm.auth_uid = auth.uid()
     and hm.hive_id = new.hive_id
     and hm.status = 'active'
   limit 1;

  if v_name is not null then
    new.worker_name := v_name;      -- the session's name for THIS hive, never the payload's
  end if;
  new.auth_uid := auth.uid();       -- attribution FK always the caller's own
  return new;
end $function$;

drop trigger if exists trg_inventory_tx_attribution on public.inventory_transactions;
create trigger trg_inventory_tx_attribution
  before insert on public.inventory_transactions
  for each row execute function public.derive_inventory_tx_attribution();

-- One-time repair of existing misattributed rows: where the row carries an auth_uid whose
-- hive-membership name disagrees with the stored worker_name, restore the member's name.
-- (Rows with no auth_uid are seeder history — attribution as stated, untouched.)
update public.inventory_transactions tx
   set worker_name = hm.worker_name
  from public.hive_members hm
 where tx.auth_uid is not null
   and hm.auth_uid = tx.auth_uid
   and hm.hive_id = tx.hive_id
   and hm.status = 'active'
   and tx.worker_name is distinct from hm.worker_name;
