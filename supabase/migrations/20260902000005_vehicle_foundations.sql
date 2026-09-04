-- VEHICLE SEED M2+M3+M5 (2026-09-02): the minimum schema for a real vehicle on the platform.
-- Design (approved plan): a car is an ASSET — no new silo. Three additions:
--   M2: asset_nodes.vehicle_meta jsonb — VIN/plate/year/odometer/registration/insurance live here,
--       NOT in external_ids (that bag is CMMS-typed: asset-hub renders every key as a sync pill and
--       warns 'no sync on record' — a semantic collision confirmed in exploration).
--   M3: mileage-based PM primitives — pm_scope_items.interval_km + interval_kind, and
--       pm_completions.meter_at_completion (without which "last service + 5,000 km" is uncomputable).
--   M5: equipment_reading_templates 'Vehicle' rows (odometer/fuel land on logbook with ZERO page
--       code — the reading fields are DB-driven) + a monotonic odometer trigger: a logbook entry
--       carrying readings_json.odometer_km rolls the asset's vehicle_meta.odometer_km FORWARD only
--       (never backwards — a typo'd 12,540 after 125,400 must not rewind the truth).

-- ── M2: the vehicle master carrier ──────────────────────────────────────────────────────────────
alter table public.asset_nodes add column if not exists vehicle_meta jsonb;

-- ── M3: mileage PM primitives ───────────────────────────────────────────────────────────────────
alter table public.pm_scope_items add column if not exists interval_km numeric check (interval_km > 0);
alter table public.pm_scope_items add column if not exists interval_kind text not null default 'calendar'
  check (interval_kind in ('calendar','meter','both'));
alter table public.pm_completions add column if not exists meter_at_completion numeric check (meter_at_completion >= 0);

-- ── M5a: vehicle reading fields (logbook picks these up automatically by category) ──────────────
insert into public.equipment_reading_templates (category, reading_key, label, unit, placeholder, sort_order)
select v.category, v.reading_key, v.label, v.unit, v.placeholder, v.sort_order
from (values
  ('Vehicle', 'odometer_km', 'Odometer', 'km', '125400', 1),
  ('Vehicle', 'fuel_l',      'Fuel added', 'L', '52.3',   2)
) as v(category, reading_key, label, unit, placeholder, sort_order)
where not exists (
  select 1 from public.equipment_reading_templates t
  where t.category = v.category and t.reading_key = v.reading_key
);

-- ── M5b: monotonic odometer roll-forward ────────────────────────────────────────────────────────
create or replace function public.roll_vehicle_odometer()
returns trigger
language plpgsql
security definer
set search_path = public
as $function$
declare v_km numeric; v_cur numeric;
begin
  if new.asset_node_id is null or new.readings_json is null then return new; end if;
  v_km := nullif(new.readings_json->>'odometer_km','')::numeric;
  if v_km is null or v_km <= 0 then return new; end if;
  select nullif(vehicle_meta->>'odometer_km','')::numeric into v_cur
    from public.asset_nodes where id = new.asset_node_id;
  -- FORWARD ONLY: a lower reading is kept on the entry (the record of what was typed) but never
  -- rewinds the asset's meter — the PM due-engine must not un-due a service on a typo.
  if v_cur is null or v_km > v_cur then
    update public.asset_nodes
       set vehicle_meta = coalesce(vehicle_meta, '{}'::jsonb)
             || jsonb_build_object('odometer_km', v_km, 'odometer_at', now()),
           updated_at = now()
     where id = new.asset_node_id;
  end if;
  return new;
end $function$;

drop trigger if exists trg_roll_vehicle_odometer on public.logbook;
create trigger trg_roll_vehicle_odometer
  after insert on public.logbook
  for each row execute function public.roll_vehicle_odometer();
