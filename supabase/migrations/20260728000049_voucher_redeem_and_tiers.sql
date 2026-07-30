-- ─────────────────────────────────────────────────────────────────────────────
-- SERVICE HAILING P6b: voucher redemption (D7/D8) + provider TIERS (§1c, Uber-Pro
-- model) — both with NO forgeable state:
--   * redeem_service_voucher: completion-gated, own-party-only, limit-enforced;
--     the redemption reimburses the PROVIDER the discount as wallet credits
--     (provider stays whole; the platform funds acquisition from its margin);
--   * tier is COMPUTED in the truth view from verified completions + guarded
--     ratings (bronze <10 done · silver ≥10 · gold ≥25 with ★≥4.5) — like the
--     rating itself, there is no stored tier to forge; perks (commission
--     discounts, priority) are D9 Ian-tunables applied where the tier is READ.
-- ─────────────────────────────────────────────────────────────────────────────
create or replace function public.redeem_service_voucher(p_code text, p_request_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_v public.service_vouchers%rowtype;
  v_req public.service_requests%rowtype;
  v_base numeric(12,2);
  v_discount numeric(12,2);
  v_uses int;
  v_mine int;
begin
  select * into v_v from public.service_vouchers where upper(code) = upper(trim(p_code)) and active;
  if v_v.id is null then return jsonb_build_object('redeemed', false, 'reason', 'unknown_or_inactive_code'); end if;
  if v_v.expires_at is not null and v_v.expires_at < now() then
    return jsonb_build_object('redeemed', false, 'reason', 'expired');
  end if;
  select * into v_req from public.service_requests where id = p_request_id;
  if v_req.id is null or v_req.client_auth_uid is distinct from auth.uid() then
    return jsonb_build_object('redeemed', false, 'reason', 'not_your_request');
  end if;
  if v_req.status not in ('completed','settled') then
    return jsonb_build_object('redeemed', false, 'reason', 'job_not_completed');
  end if;
  if v_v.segment is not null and v_v.segment <> v_req.segment then
    return jsonb_build_object('redeemed', false, 'reason', 'wrong_segment');
  end if;
  select count(*) into v_uses from public.service_voucher_redemptions where voucher_id = v_v.id;
  if v_v.max_uses is not null and v_uses >= v_v.max_uses then
    return jsonb_build_object('redeemed', false, 'reason', 'fully_used');
  end if;
  select count(*) into v_mine from public.service_voucher_redemptions
   where voucher_id = v_v.id and consumer_auth_uid = auth.uid();
  if v_mine >= v_v.per_user_limit then
    return jsonb_build_object('redeemed', false, 'reason', 'limit_reached');
  end if;
  select coalesce(
           (select o.price from public.service_offers o
             where o.request_id = v_req.id and o.status = 'selected' and o.price is not null
             order by o.updated_at desc limit 1),
           (select c.base_rate from public.service_catalog c where c.id = v_req.catalog_item_id),
           0)
    into v_base;
  v_discount := case when v_v.kind = 'percent' then round(v_base * v_v.value / 100.0, 2)
                     else least(v_v.value, v_base) end;
  if v_discount <= 0 then return jsonb_build_object('redeemed', false, 'reason', 'nothing_to_discount'); end if;
  begin
    insert into public.service_voucher_redemptions (voucher_id, request_id, consumer_auth_uid, amount)
    values (v_v.id, p_request_id, auth.uid(), v_discount);
  exception when unique_violation then
    return jsonb_build_object('redeemed', false, 'reason', 'already_redeemed_on_this_job');
  end;
  if v_req.matched_provider_id is not null then
    insert into public.service_credit_ledger (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
    values ('provider', v_req.matched_provider_id, 'voucher_reimburse', v_discount, 'voucher', v_v.id,
            'Voucher ' || v_v.code || ' reimbursement (client discount covered by the platform)');
  end if;
  return jsonb_build_object('redeemed', true, 'discount', v_discount, 'code', v_v.code);
end $$;
grant execute on function public.redeem_service_voucher(text, uuid) to authenticated;

-- computed TIER joins the truth view (v3)
drop view if exists public.v_service_provider_truth;
create view public.v_service_provider_truth
with (security_invoker = false) as
select
  sp.id, sp.provider_type, sp.worker_name, sp.hive_id, sp.display_name, sp.contact,
  sp.categories, sp.service_areas, sp.base_lat, sp.base_lng, sp.availability,
  sp.verified, sp.verified_at, sp.created_at,
  coalesce(j.completed_jobs, 0) as completed_jobs,
  rv.rating_avg, coalesce(rv.rating_count, 0) as rating_count,
  case when coalesce(j.completed_jobs, 0) >= 25 and coalesce(rv.rating_avg, 0) >= 4.5 then 'gold'
       when coalesce(j.completed_jobs, 0) >= 10 then 'silver'
       else 'bronze' end as tier,
  1 as _source_count, sp.updated_at as _freshness_ts,
  'service_provider_truth:v3' as _canonical_version
from public.service_providers sp
left join (
  select matched_provider_id, count(*) as completed_jobs
  from public.service_requests where status in ('completed','settled')
  group by matched_provider_id
) j on j.matched_provider_id = sp.id
left join (
  select r.matched_provider_id, round(avg(mr.rating)::numeric, 2) as rating_avg, count(*) as rating_count
  from public.marketplace_reviews mr
  join public.service_requests r on r.id = mr.request_id
  where mr.direction = 'client_to_provider'
  group by r.matched_provider_id
) rv on rv.matched_provider_id = sp.id;
grant select on public.v_service_provider_truth to anon, authenticated;

insert into public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values ('service_hailing', 'rpc', 'redeem_service_voucher', 'marketplace', 'on_demand',
        '{"signature": "redeem_service_voucher(p_code text, p_request_id uuid) RETURNS jsonb", "side_effects": ["service_voucher_redemptions insert", "provider voucher_reimburse ledger credit"]}'::jsonb,
        'Completion-gated voucher redemption; reimburses the provider the discount (platform-funded acquisition, D8).')
on conflict do nothing;
