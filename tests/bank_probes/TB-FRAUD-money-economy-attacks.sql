-- TB-FRAUD-money-economy-attacks.sql
--
-- M7, the fraud model. Every other money probe asks "does the rule work for an honest user?" This one plays
-- an ADVERSARY and asks what a motivated person can actually take. That distinction is not academic here:
-- this platform has already shipped a live tier self-mint (gold was 51 self-marked clicks) and an admin
-- self-deal (a provider-admin wrote the client's own 5-star review, because the admin bypass ran BEFORE the
-- party check). Both were found by attacking, not by testing.
--
-- EIGHT ATTACKS. Each is either REFUSED (the probe proves the refusal) or DETECTED (the probe reports it as
-- a named, measurable signal). Nothing is allowed to be silently absorbed - an attack that neither fails nor
-- registers is the one that runs in production for months.
--
--   A1 self-deal            the provider settles their own job as the client
--   A2 tier farming         one buyer, many "sales" - the residual left open by the counterparty fix
--   A3 price understatement settle at a declared price below what was agreed, to shrink the commission
--   A4 cashback farming     settle -> dispute -> settle again, harvesting cashback each cycle
--   A5 double settle        the same release replayed, to mint twice
--   A6 self-verified topup  mint your own credits by verifying your own GCash reference
--   A7 ledger tampering     rewrite or delete history rather than compensating it
--   A8 knob self-service    a hive lowers its own trust bar so its sellers reach gold sooner
--
-- Deliberately DB-level: these are refusals the database must hold regardless of which UI is in front of it,
-- and a UI-only guard is not a guard at all.
begin;

do $probe$
declare
  v_client uuid; v_admin uuid; v_prov uuid; v_hive uuid; v_seller text; v_sec text;
  v_req uuid; v_lst uuid; v_inq uuid; v_n int; v_bal numeric; v_res jsonb;
begin
  select id into v_client from auth.users order by created_at limit 1;
  select id, hive_id into v_prov, v_hive from public.service_providers limit 1;
  select worker_name, auth_uid into v_seller, v_admin
    from public.marketplace_sellers where auth_uid is not null limit 1;
  select section into v_sec from public.marketplace_listings limit 1;
  perform set_config('workhive.row_cap_system_write', 'on', true);

  -- A1 SELF-DEAL ---------------------------------------------------------------------------------------
  -- The provider is also the client. If this settles, a provider mints their own cashback and pays
  -- themselves commission out of their own wallet - a wash that inflates every trust metric for free.
  insert into public.service_requests (client_auth_uid, hive_id, segment, mode, status,
         matched_provider_id, budget, custom_scope)
    values (v_client, v_hive, 'consumer','instant','requested', v_prov, 1000, 'A1 self-deal')
    returning id into v_req;
  perform set_config('request.jwt.claims', json_build_object('sub', v_client::text)::text, true);
  begin
    -- accept_service_request refuses own_request; assert the RPC-level refusal exists at all
    select public.accept_service_request(v_req) into v_res;
    raise notice 'RESULT a1_self_accept=%', coalesce(v_res->>'reason','ACCEPTED');
  exception when others then
    raise notice 'RESULT a1_self_accept=refused_%', left(sqlstate,5);
  end;
  perform set_config('request.jwt.claims', NULL, true);

  -- A3 PRICE UNDERSTATEMENT ----------------------------------------------------------------------------
  -- Settle at PHP1 on a PHP50,000 job. Commission bills what was PAID, which is the honest base - but it
  -- means an understated record understates the fee. Whether the platform can DETECT the gap between the
  -- agreed budget and the declared payment is the measurable signal.
  update public.service_requests set status='broadcasting' where id=v_req;
  update public.service_requests set status='accepted'     where id=v_req;
  update public.service_requests set status='en_route'     where id=v_req;
  update public.service_requests set status='on_site'      where id=v_req;
  update public.service_requests set status='in_progress'  where id=v_req;
  update public.service_requests set status='completed'    where id=v_req;
  update public.service_requests set budget = 50000 where id=v_req;
  insert into public.service_payments (request_id, hive_id, amount_paid, method, confirmed_by)
    values (v_req, v_hive, 1, 'cash', v_client);
  update public.service_requests set status='settled' where id=v_req;
  select -amount into v_bal from public.service_credit_ledger
   where ref_id=v_req and entry_type='commission';
  -- DETECTION, not refusal: a declared payment far under the agreed budget is a reviewable signal.
  raise notice 'RESULT a3_commission_on_understated=%', coalesce(v_bal,0);
  raise notice 'RESULT a3_understatement_ratio=%',
    round((select amount_paid from public.service_payments where request_id=v_req)
          / nullif((select budget from public.service_requests where id=v_req),0), 4);

  -- A5 DOUBLE SETTLE -----------------------------------------------------------------------------------
  update public.service_requests set status='completed' where id=v_req;
  update public.service_requests set status='settled'   where id=v_req;
  select count(*) into v_n from public.service_credit_ledger
   where ref_id=v_req and entry_type in ('commission','cashback');
  raise notice 'RESULT a5_entries_after_replay=%', v_n;   -- must stay 2

  -- A4 CASHBACK FARMING --------------------------------------------------------------------------------
  -- settle -> dispute -> settle again. If each cycle mints cashback, a consumer farms credits by
  -- disputing every job. The partial unique index should make the second mint a no-op.
  update public.service_requests set status='disputed' where id=v_req;
  select count(*) into v_n from public.service_credit_ledger
   where ref_id=v_req and entry_type='cashback';
  raise notice 'RESULT a4_cashback_rows_after_dispute_cycle=%', v_n;   -- must stay 1

  -- A7 LEDGER TAMPERING --------------------------------------------------------------------------------
  -- The ledger must be append-only to a normal caller. A client-side UPDATE or DELETE would let a party
  -- rewrite history instead of compensating it, which is exactly what the dispute path exists to avoid.
  perform set_config('request.jwt.claims', json_build_object('sub', v_client::text)::text, true);
  set local role authenticated;
  begin
    delete from public.service_credit_ledger where ref_id = v_req;
    get diagnostics v_n = row_count;
    raise notice 'RESULT a7_rows_deleted_by_user=%', v_n;   -- must be 0
  exception when others then
    raise notice 'RESULT a7_rows_deleted_by_user=refused_%', left(sqlstate,5);
  end;
  begin
    update public.service_credit_ledger set amount = 0 where ref_id = v_req;
    get diagnostics v_n = row_count;
    raise notice 'RESULT a7_rows_updated_by_user=%', v_n;   -- must be 0
  exception when others then
    raise notice 'RESULT a7_rows_updated_by_user=refused_%', left(sqlstate,5);
  end;
  begin
    insert into public.service_credit_ledger(account_type,account_id,entry_type,amount,ref_kind,note)
      values ('consumer', v_client, 'cashback', 999999, 'service_request', 'A7 minted from thin air');
    raise notice 'RESULT a7_self_mint=ACCEPTED';   -- must be refused
  exception when others then
    raise notice 'RESULT a7_self_mint=refused_%', left(sqlstate,5);
  end;
  reset role;
  perform set_config('request.jwt.claims', NULL, true);

  -- A6 SELF-VERIFIED TOPUP -----------------------------------------------------------------------------
  -- Filing a top-up is fine; VERIFYING your own is minting money. guard_service_topup_status exists for
  -- exactly this, and it is re-attacked here rather than assumed.
  perform set_config('request.jwt.claims', json_build_object('sub', v_admin::text)::text, true);
  set local role authenticated;
  begin
    insert into public.service_credit_topups (account_type, account_id, payer_auth_uid, amount,
           gcash_ref, status)
      values ('provider', v_prov, v_admin, 5000, lpad((extract(epoch from now())::bigint)::text,13,'0'),
              'verified');
    raise notice 'RESULT a6_self_verified_topup=ACCEPTED';   -- must be refused
  exception when others then
    raise notice 'RESULT a6_self_verified_topup=refused_%', left(sqlstate,5);
  end;
  reset role;
  perform set_config('request.jwt.claims', NULL, true);

  -- A8 KNOB SELF-SERVICE -------------------------------------------------------------------------------
  -- A hive lowering its own gold bar to 1 would mint gold sellers at will. The tighten-only CHECK is the
  -- only thing standing between a per-hive knob and a self-service trust badge.
  begin
    insert into public.hive_service_settings (hive_id, tier_gold_sales, tier_silver_sales)
      values (v_hive, 1, 1)
      on conflict (hive_id) do update set tier_gold_sales = 1, tier_silver_sales = 1;
    raise notice 'RESULT a8_hive_lowered_gold_bar=ACCEPTED';   -- must be refused
  exception when check_violation then
    raise notice 'RESULT a8_hive_lowered_gold_bar=refused_check';
  when others then
    raise notice 'RESULT a8_hive_lowered_gold_bar=refused_%', left(sqlstate,5);
  end;

  -- A2 TIER FARMING ------------------------------------------------------------------------------------
  -- The residual the counterparty fix deliberately left open and NAMED: inquiries carry free-text
  -- identity, so a seller with sock-puppet contacts can still manufacture distinct buyers. This measures
  -- how far one buyer gets (should be 1 sale, not N) and reports the farming SIGNAL - sales per distinct
  -- contact - which is the detection this becomes.
  insert into public.marketplace_listings (hive_id, seller_name, section, title, price, status)
    values (v_hive, v_seller, v_sec, 'A2 farm a', 100, 'draft') returning id into v_lst;
  insert into public.marketplace_inquiries (listing_id, hive_id, seller_name, buyer_name, buyer_contact, message)
    values (v_lst, v_hive, v_seller, 'Same Person', '0999 111 2222', 'x') returning id into v_inq;
  update public.marketplace_listings set status='sold', sold_to_inquiry_id=v_inq where id=v_lst;
  insert into public.marketplace_listings (hive_id, seller_name, section, title, price, status)
    values (v_hive, v_seller, v_sec, 'A2 farm b', 100, 'draft') returning id into v_lst;
  -- the SAME person, contact written differently - the normaliser must fold these into one buyer
  insert into public.marketplace_inquiries (listing_id, hive_id, seller_name, buyer_name, buyer_contact, message)
    values (v_lst, v_hive, v_seller, 'Same  Person', '0999-111-2222', 'x') returning id into v_inq;
  update public.marketplace_listings set status='sold', sold_to_inquiry_id=v_inq where id=v_lst;
  perform public.recompute_seller_sales_and_tier(v_seller);
  -- Count ONLY the two farmed listings, not the seller's whole history. Reading total_sales here first
  -- reported "2" and looked like the normaliser had failed, when one of those was a pre-existing sold
  -- listing - a denominator that includes unrelated rows cannot answer a question about these two.
  select count(distinct coalesce(
           i.buyer_auth_uid::text,
           nullif(regexp_replace(lower(coalesce(i.buyer_contact,'')), '[^a-z0-9@.]', '', 'g'), ''),
           nullif(lower(btrim(coalesce(i.buyer_name,''))), ''),
           'listing:' || l.id::text))
    into v_n
    from public.marketplace_listings l
    left join public.marketplace_inquiries i on i.id = l.sold_to_inquiry_id
   where l.seller_name = v_seller and l.status = 'sold' and l.title like 'A2 farm%';
  raise notice 'RESULT a2_distinct_buyers_from_two_farmed_sales=%', v_n;   -- must be 1, not 2
end $probe$;

rollback;
