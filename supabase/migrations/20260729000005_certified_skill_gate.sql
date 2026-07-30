-- =====================================================================
-- J20 · CERTIFIED-SKILL GATE - a premium trade needs a real badge, not a self-declaration
-- =====================================================================
-- §1c promised the Grab-Academy hook: "certified skills gate premium job categories; a Certified
-- badge on provider cards". What shipped was only the skillmatrix "become a provider" BRIDGE -
-- a provider still self-declares `categories[]` with nothing checking it, so anyone could tick
-- "Calibration" and accept calibration work on a plant's instruments. The arc scoreboard scored
-- J20 at 20% for exactly that.
--
-- THE MAPPING ALREADY EXISTS: skill_badges.discipline uses the same vocabulary as
-- service_catalog.category (Mechanical / Electrical / HVAC / Calibration / Generator / Welding),
-- and badges carry a LEVEL + an exam score - they are earned through skill_exam_keys, not typed.
-- So the gate is a join, not a new certification system (reuse, never reinvent).
--
-- SCOPE: only categories a plant would genuinely want certified are gated. Everything else stays
-- open, so this raises the floor without shutting ordinary trades out of the marketplace.

BEGIN;

-- 1. Which catalog items demand a badge --------------------------------------------------
alter table public.service_catalog
  add column if not exists requires_cert_level integer
    check (requires_cert_level is null or requires_cert_level between 1 and 5);

comment on column public.service_catalog.requires_cert_level is
  'J20: minimum skill_badges.level in the matching discipline before a provider may ACCEPT this service. NULL = open to any provider.';

-- Instruments + gensets are the two a plant would not hand to an unbadged stranger.
update public.service_catalog set requires_cert_level = 2
 where segment = 'industrial' and category in ('Calibration', 'Generator')
   and requires_cert_level is distinct from 2;

-- 2. Is this provider certified for this category? ---------------------------------------
-- A freelancer qualifies on their OWN badge. A hive company qualifies when ANY active member
-- holds it - the company is the contracting party and dispatches whoever is badged.
create or replace function public.provider_is_certified_for(p_provider_id uuid, p_category text, p_min_level integer)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select case
    when p_min_level is null then true
    else exists (
      select 1
        from public.service_providers sp
        left join public.skill_badges b_self
               on sp.provider_type = 'freelancer'
              and (b_self.auth_uid = sp.auth_uid or b_self.worker_name = sp.worker_name)
              and b_self.discipline = p_category
              and b_self.level >= p_min_level
        left join public.hive_members hm
               on sp.provider_type = 'hive' and hm.hive_id = sp.hive_id and hm.status = 'active'
        left join public.skill_badges b_member
               on b_member.worker_name = hm.worker_name
              and b_member.discipline = p_category
              and b_member.level >= p_min_level
       where sp.id = p_provider_id
         and (b_self.id is not null or b_member.id is not null)
    )
  end;
$$;

comment on function public.provider_is_certified_for(uuid, text, integer) is
  'J20: does this provider hold (freelancer) or employ (hive company) a skill badge at >= the required level in the given discipline? Badges are earned via skill_exam_keys, so this cannot be self-asserted.';

grant execute on function public.provider_is_certified_for(uuid, text, integer) to authenticated;

-- 3. Enforce it at ACCEPT time -----------------------------------------------------------
-- SURGICAL, not a rewrite. The block below is the function's EXACT current definition with only
-- the certification check inserted. Two things this deliberately does NOT do:
--   * change the signature - dropping the p_eta_minutes default would create a SECOND overload
--     and PostgREST answers PGRST203 for every caller, killing the dispatch endpoint outright;
--   * touch the atomic race (status = 'broadcasting' + `v_won := found`), the offer bookkeeping,
--     or the availability follow-through.

-- J20 surgical patch: the EXACT current definition of accept_service_request with ONLY the
-- certification gate inserted. Signature (p_request_id uuid, p_eta_minutes integer DEFAULT NULL)
-- is preserved verbatim - changing it would mint a SECOND overload and PostgREST would answer
-- PGRST203 for every caller (the endpoint-killing class already learned once on this platform).

CREATE OR REPLACE FUNCTION public.accept_service_request(p_request_id uuid, p_eta_minutes integer DEFAULT NULL::integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public', 'extensions'
AS $function$
declare
  v_provider public.service_providers%rowtype;
  v_req public.service_requests%rowtype;
  v_won boolean;
  v_cert_cat text;
  v_cert_level integer;
begin
  -- caller must own an ONLINE provider identity
  select sp.* into v_provider
  from public.service_providers sp
  where sp.id in (select public.my_service_provider_ids())
    and sp.availability = 'online'
  order by sp.verified desc, sp.created_at
  limit 1;
  if v_provider.id is null then
    return jsonb_build_object('accepted', false, 'reason', 'no_online_provider_identity');
  end if;

  select r.* into v_req from public.service_requests r where r.id = p_request_id;
  if v_req.id is null then
    return jsonb_build_object('accepted', false, 'reason', 'not_found');
  end if;
  if v_req.client_auth_uid = auth.uid() then
    return jsonb_build_object('accepted', false, 'reason', 'own_request');
  end if;
  -- eligibility: category overlap (catalog requests) + radius when both points exist
  if v_req.catalog_item_id is not null and not exists (
    select 1 from public.service_catalog c
    where c.id = v_req.catalog_item_id
      and (c.category = any (v_provider.categories))
  ) then
    return jsonb_build_object('accepted', false, 'reason', 'category_mismatch');
  end if;
  if v_req.location is not null and v_provider.base_location is not null
     and not st_dwithin(v_req.location, v_provider.base_location, v_req.broadcast_radius_m * 4) then
    return jsonb_build_object('accepted', false, 'reason', 'out_of_radius');
  end if;

  -- J20 CERTIFIED-SKILL GATE: a premium trade needs an EARNED badge, not a self-declared
  -- categories[] entry. Checked after category overlap (so the message is the specific one) and
  -- before the money gate. Open categories have requires_cert_level NULL and skip this entirely.
  if v_req.catalog_item_id is not null then
    select c.category, c.requires_cert_level into v_cert_cat, v_cert_level
      from public.service_catalog c where c.id = v_req.catalog_item_id;
    if v_cert_level is not null
       and not public.provider_is_certified_for(v_provider.id, v_cert_cat, v_cert_level) then
      return jsonb_build_object('accepted', false, 'reason', 'not_certified',
                                'category', v_cert_cat, 'required_level', v_cert_level);
    end if;
  end if;

  -- P6b (mig 48 adjunct): a provider in commission DEBT cannot accept until they top up
  if public.provider_credit_balance(v_provider.id) < 0 then
    return jsonb_build_object('accepted', false, 'reason', 'insufficient_credits',
                              'balance', public.provider_credit_balance(v_provider.id));
  end if;

  -- announce to the state-machine guard for THIS transaction only
  perform set_config('workhive.service_system_write', 'on', true);

  -- ★ the atomic race: exactly one caller flips broadcasting -> accepted
  update public.service_requests
     set status = 'accepted',
         matched_provider_id = v_provider.id,
         accepted_at = now(),
         updated_at = now()
   where id = p_request_id
     and status = 'broadcasting';
  v_won := found;

  if not v_won then
    -- 0 rows = lost the race (or state moved) — surfaced honestly, never silently
    return jsonb_build_object('accepted', false, 'reason', 'lost_race_or_closed',
                              'status', (select status from public.service_requests where id = p_request_id));
  end if;

  -- record the winning accept; expire other pending instant-accepts
  insert into public.service_offers (request_id, provider_id, kind, eta_minutes, status)
  values (p_request_id, v_provider.id, 'accept', p_eta_minutes, 'selected')
  on conflict (request_id, provider_id)
  do update set kind = 'accept', status = 'selected', eta_minutes = excluded.eta_minutes, updated_at = now();
  update public.service_offers
     set status = 'expired', updated_at = now()
   where request_id = p_request_id and provider_id <> v_provider.id and status = 'pending' and kind = 'accept';

  -- availability follows the job (mirrors the sync trigger for direct RPC path)
  update public.service_providers set availability = 'on_job', updated_at = now()
   where id = v_provider.id and availability = 'online';

  return jsonb_build_object('accepted', true, 'request_id', p_request_id, 'provider_id', v_provider.id);
end $function$;

COMMIT;
