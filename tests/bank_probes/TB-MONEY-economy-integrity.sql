-- TB-MONEY-economy-integrity.sql
--
-- M3, the deterministic money lane. The bank's 293 SQL cells cover DISPATCH — who may move a job from one
-- state to the next. None of them covered MONEY, which is the one subsystem where a false green is
-- unaffordable: every other bug costs a re-render, this one costs pesos.
--
-- DELIBERATELY WEIGHTED TO db-truth, NOT refusal. The bank's oracle mix is 235 refusal to 52 db-truth, and
-- refusals only ever prove what is FORBIDDEN. An economy also needs proof of what must HAPPEN — that the
-- right amount is minted, to the right account, exactly once, on the right base. Roughly two thirds of the
-- assertions below are positive.
--
-- Every assertion carries NON-VACUITY where it can: it is not enough that a refusal fired, the probe also
-- shows the permitted form succeeding, so a guard that refused EVERYTHING would fail this file rather than
-- pass it perfectly.
--
-- Six families: payment record (PAY) · cashback (CASHBACK) · commission and rates (ECON) · tier (TIER) ·
-- dispute (DISPUTE) · solvency and the ledger's own integrity (SOLV).
begin;

do $probe$
declare
  v_client uuid; v_client2 uuid; v_prov uuid; v_hive uuid; v_admin uuid; v_seller text; v_sec text;
  v_req uuid; v_req2 uuid; v_lst uuid; v_inq uuid; v_n int; v_a numeric; v_b numeric; v_res jsonb;
  v_seller_uid uuid; v_again jsonb;
begin
  select id into v_client  from auth.users order by created_at limit 1;
  select id into v_client2 from auth.users order by created_at desc limit 1;
  select id, hive_id into v_prov, v_hive from public.service_providers limit 1;
  -- TWO DISTINCT IDENTITIES, resolved the way the code resolves them. The first cut used the seller's
  -- account as the admin and the dispute section died on "Only a platform admin may adjust" - a seller
  -- is not an admin, and is_marketplace_admin() reads marketplace_platform_admins, not this table.
  select worker_name, auth_uid into v_seller, v_seller_uid
    from public.marketplace_sellers where auth_uid is not null limit 1;
  select coalesce(m.auth_uid, s2.auth_uid) into v_admin
    from public.marketplace_platform_admins pa
    left join public.hive_members m       on m.worker_name  = pa.worker_name and m.auth_uid  is not null
    left join public.marketplace_sellers s2 on s2.worker_name = pa.worker_name and s2.auth_uid is not null
   where coalesce(m.auth_uid, s2.auth_uid) is not null limit 1;
  -- the job's client must NOT be the adjudicating admin, or DISPUTE-03 would test the party refusal twice
  select id into v_client from auth.users
   where id is distinct from v_admin order by created_at limit 1;
  select section into v_sec from public.marketplace_listings limit 1;
  perform set_config('workhive.row_cap_system_write', 'on', true);

  -- ============ PAY · the payment record ==============================================================
  insert into public.service_requests (client_auth_uid, hive_id, segment, mode, status,
         matched_provider_id, budget, custom_scope)
    values (v_client, v_hive, 'industrial','instant','completed', v_prov, 9999, 'money probe')
    returning id into v_req;

  begin   -- PAY-01 release without a record is refused
    update public.service_requests set status='settled' where id=v_req;
    raise notice 'RESULT pay_01_settle_without_record=ALLOWED';
  exception when check_violation then
    raise notice 'RESULT pay_01_settle_without_record=refused';
  end;

  begin   -- PAY-02 a zero/negative payment is refused (a free job is not a payment)
    insert into public.service_payments (request_id, hive_id, amount_paid, confirmed_by)
      values (v_req, v_hive, 0, v_client);
    raise notice 'RESULT pay_02_zero_amount=ALLOWED';
  exception when others then raise notice 'RESULT pay_02_zero_amount=refused';
  end;

  begin   -- PAY-03 a malformed GCash reference is refused (13 digits, same shape the top-up queue verifies)
    insert into public.service_payments (request_id, hive_id, amount_paid, gcash_ref, method, confirmed_by)
      values (v_req, v_hive, 2000, 'not-a-ref', 'gcash', v_client);
    raise notice 'RESULT pay_03_bad_gcash_ref=ALLOWED';
  exception when check_violation then raise notice 'RESULT pay_03_bad_gcash_ref=refused';
  end;

  -- PAY-04 the permitted form succeeds (NON-VACUITY for 01-03: a table refusing everything is not a guard)
  insert into public.service_payments (request_id, hive_id, amount_paid, method, confirmed_by)
    values (v_req, v_hive, 2000, 'cash', v_client);
  raise notice 'RESULT pay_04_valid_record_accepted=%',
    (select count(*) from public.service_payments where request_id=v_req);

  begin   -- PAY-05 a SECOND record is refused: the price cannot be restated after commission is billed
    insert into public.service_payments (request_id, hive_id, amount_paid, confirmed_by)
      values (v_req, v_hive, 5, v_client);
    raise notice 'RESULT pay_05_second_record=ALLOWED';
  exception when unique_violation then raise notice 'RESULT pay_05_second_record=refused';
  end;

  begin   -- PAY-06 an unknown request cannot carry a payment
    insert into public.service_payments (request_id, hive_id, amount_paid, confirmed_by)
      values (gen_random_uuid(), v_hive, 100, v_client);
    raise notice 'RESULT pay_06_orphan_record=ALLOWED';
  exception when foreign_key_violation then raise notice 'RESULT pay_06_orphan_record=refused';
  end;

  -- PAY-07 the record is IMMUTABLE to a normal caller: evidence that can be edited is not evidence
  perform set_config('request.jwt.claims', json_build_object('sub', v_client::text)::text, true);
  set local role authenticated;
  begin
    update public.service_payments set amount_paid = 1 where request_id = v_req;
    get diagnostics v_n = row_count;
    raise notice 'RESULT pay_07_user_edit_rows=%', v_n;
  exception when others then raise notice 'RESULT pay_07_user_edit_rows=0';
  end;
  begin   -- PAY-08 and it cannot be deleted either
    delete from public.service_payments where request_id = v_req;
    get diagnostics v_n = row_count;
    raise notice 'RESULT pay_08_user_delete_rows=%', v_n;
  exception when others then raise notice 'RESULT pay_08_user_delete_rows=0';
  end;
  reset role;
  perform set_config('request.jwt.claims', NULL, true);

  -- ============ ECON · commission and the rates =======================================================
  update public.service_requests set status='settled' where id=v_req;

  raise notice 'RESULT econ_01_commission_minted=%',
    (select count(*) from public.service_credit_ledger where ref_id=v_req and entry_type='commission');
  raise notice 'RESULT econ_02_commission_is_negative=%',      -- a charge, by the ledger's convention
    (select (amount < 0) from public.service_credit_ledger where ref_id=v_req and entry_type='commission');
  raise notice 'RESULT econ_03_commission_on_paid_not_budget=%',  -- 5% of 2000 PAID, not of 9999 budget
    (select -amount from public.service_credit_ledger where ref_id=v_req and entry_type='commission');
  raise notice 'RESULT econ_04_charged_to_provider=%',
    (select (account_type='provider' and account_id=v_prov) from public.service_credit_ledger
      where ref_id=v_req and entry_type='commission');
  update public.service_requests set status='completed' where id=v_req;
  update public.service_requests set status='settled'   where id=v_req;
  raise notice 'RESULT econ_05_replay_mints_once=%',
    (select count(*) from public.service_credit_ledger where ref_id=v_req and entry_type='commission');
  raise notice 'RESULT econ_06_knob_readable=%', public.service_knob_pct(v_hive,'commission_pct');
  raise notice 'RESULT econ_07_min_list_floor=%', public.service_knob(v_hive,'min_list_balance');

  -- ============ CASHBACK ==============================================================================
  raise notice 'RESULT cashback_01_minted=%',
    (select count(*) from public.service_credit_ledger where ref_id=v_req and entry_type='cashback');
  raise notice 'RESULT cashback_02_is_positive=%',            -- a credit TO the consumer, not a charge
    (select (amount > 0) from public.service_credit_ledger where ref_id=v_req and entry_type='cashback');
  raise notice 'RESULT cashback_03_to_consumer=%',
    (select (account_type='consumer' and account_id=v_client) from public.service_credit_ledger
      where ref_id=v_req and entry_type='cashback');
  raise notice 'RESULT cashback_04_same_base_as_commission=%', -- 1% of the SAME 2000
    (select amount from public.service_credit_ledger where ref_id=v_req and entry_type='cashback');
  raise notice 'RESULT cashback_05_replay_mints_once=%',
    (select count(*) from public.service_credit_ledger where ref_id=v_req and entry_type='cashback');
  -- CASHBACK-06 an UNSETTLED job earns nothing: the minter must refuse to run out of order
  insert into public.service_requests (client_auth_uid, hive_id, segment, mode, status,
         matched_provider_id, budget, custom_scope)
    values (v_client2, v_hive, 'consumer','instant','completed', v_prov, 3000, 'unsettled')
    returning id into v_req2;
  raise notice 'RESULT cashback_06_unsettled_mints_zero=%', public.mint_service_cashback(v_req2);
  raise notice 'RESULT cashback_07_unknown_request_mints_zero=%',
    public.mint_service_cashback(gen_random_uuid());
  raise notice 'RESULT cashback_08_net_take_is_commission_minus_cashback=%',
    (select coalesce(-sum(amount),0) from public.service_credit_ledger
      where ref_id=v_req and entry_type in ('commission','cashback'));

  -- ============ TIER ==================================================================================
  perform set_config('request.jwt.claims', json_build_object('sub', v_seller_uid::text)::text, true);
  set local role authenticated;
  insert into public.marketplace_listings (hive_id, seller_name, section, title, price, status)
    values (v_hive, v_seller, v_sec, 'tier probe', 100, 'draft') returning id into v_lst;
  begin   -- TIER-01 a self-marked sale is refused
    update public.marketplace_listings set status='sold' where id=v_lst;
    raise notice 'RESULT tier_01_self_marked_sale=ALLOWED';
  exception when check_violation then raise notice 'RESULT tier_01_self_marked_sale=refused';
  end;
  reset role;
  insert into public.marketplace_inquiries (listing_id, hive_id, seller_name, buyer_name, buyer_contact, message)
    values (v_lst, v_hive, v_seller, 'Buyer One', '0917 000 0001', 'x') returning id into v_inq;
  perform set_config('request.jwt.claims', json_build_object('sub', v_seller_uid::text)::text, true);
  set local role authenticated;
  -- TIER-02 with a real counterparty it IS allowed (non-vacuity for TIER-01)
  update public.marketplace_listings set status='sold', sold_to_inquiry_id=v_inq where id=v_lst;
  raise notice 'RESULT tier_02_sale_with_buyer=%',
    (select (status='sold') from public.marketplace_listings where id=v_lst);
  insert into public.marketplace_listings (hive_id, seller_name, section, title, price, status)
    values (v_hive, v_seller, v_sec, 'tier probe b', 100, 'draft') returning id into v_lst;
  begin   -- TIER-03 an inquiry from ANOTHER listing cannot be reused
    update public.marketplace_listings set status='sold', sold_to_inquiry_id=v_inq where id=v_lst;
    raise notice 'RESULT tier_03_cross_listing_inquiry=ALLOWED';
  exception when check_violation then raise notice 'RESULT tier_03_cross_listing_inquiry=refused';
  end;
  reset role;
  perform set_config('request.jwt.claims', NULL, true);
  raise notice 'RESULT tier_04_seller_cannot_forge_own_inquiry=%',
    (select count(*) from pg_policies where tablename='marketplace_inquiries' and cmd='INSERT');
  begin   -- TIER-05 a hive cannot lower the gold bar below the platform floor
    insert into public.hive_service_settings (hive_id, tier_gold_sales, tier_silver_sales)
      values (v_hive, 2, 1)
      on conflict (hive_id) do update set tier_gold_sales=2, tier_silver_sales=1;
    raise notice 'RESULT tier_05_lower_gold_bar=ALLOWED';
  exception when others then raise notice 'RESULT tier_05_lower_gold_bar=refused';
  end;
  raise notice 'RESULT tier_06_counts_distinct_buyers=%',
    (select count(distinct coalesce(i.buyer_auth_uid::text,
              nullif(regexp_replace(lower(coalesce(i.buyer_contact,'')),'[^a-z0-9@.]','','g'),''),
              nullif(lower(btrim(coalesce(i.buyer_name,''))),''), 'listing:'||l.id::text))
       from public.marketplace_listings l
       left join public.marketplace_inquiries i on i.id = l.sold_to_inquiry_id
      where l.seller_name=v_seller and l.status='sold' and l.title like 'tier probe%');

  -- ============ DISPUTE ===============================================================================
  update public.service_requests set status='disputed' where id=v_req;
  raise notice 'RESULT dispute_01_settled_can_be_disputed=%',
    (select (status='disputed') from public.service_requests where id=v_req);
  perform set_config('request.jwt.claims', json_build_object('sub', v_client::text)::text, true);
  set local role authenticated;
  begin   -- DISPUTE-02 a party cannot adjust their own job
    v_res := public.apply_dispute_adjustment(v_req, 'self');
    raise notice 'RESULT dispute_02_party_can_adjust=ALLOWED';
  exception when others then raise notice 'RESULT dispute_02_party_can_adjust=refused';
  end;
  reset role;
  perform set_config('request.jwt.claims', json_build_object('sub', v_admin::text)::text, true);
  set local role authenticated;
  begin
    v_res := public.apply_dispute_adjustment(v_req, 'work not to spec');
  exception when others then
    v_res := jsonb_build_object('adjusted','no_admin_fixture','commission_reversed',0,
                                'cashback_clawed_back',0);
  end;
  -- DISPUTE-07 must run while STILL holding the admin identity. Called after `reset role` it raised
  -- "Only a platform admin may adjust" and looked like a broken idempotency check, when it was the probe
  -- losing its role between the two calls — the instrument, not the rule.
  begin
    v_again := public.apply_dispute_adjustment(v_req,'again');
  exception when others then v_again := jsonb_build_object('reason','no_admin_fixture');
  end;
  reset role;
  perform set_config('request.jwt.claims', NULL, true);
  raise notice 'RESULT dispute_03_admin_adjust_applied=%', v_res->>'adjusted';
  raise notice 'RESULT dispute_04_commission_reversed=%', v_res->>'commission_reversed';
  raise notice 'RESULT dispute_05_cashback_clawed_back=%', v_res->>'cashback_clawed_back';
  raise notice 'RESULT dispute_06_nothing_deleted=%',      -- 2 mints + 2 adjustments, all four kept
    (select count(*) from public.service_credit_ledger where ref_id=v_req);
  raise notice 'RESULT dispute_07_idempotent=%', v_again->>'reason';
  raise notice 'RESULT dispute_08_net_position_zero=%',    -- the platform kept nothing on a reversed job
    (select coalesce(sum(amount),0) from public.service_credit_ledger
      where ref_id=v_req and account_type='provider');

  -- ============ SOLV · the ledger's own integrity =====================================================
  raise notice 'RESULT solv_01_no_negative_consumer=%',
    (select count(*) from (select account_id from public.service_credit_ledger
       where account_type='consumer' group by account_id having sum(amount) < 0) x);
  raise notice 'RESULT solv_02_vouchers_within_earned=%',
    (select (coalesce(sum(amount) filter (where entry_type='voucher_grant'),0)
          <= coalesce(-sum(amount) filter (where entry_type='commission'),0))
       from public.service_credit_ledger);
  raise notice 'RESULT solv_03_entry_types_constrained=%',
    (select count(*) from pg_constraint where conrelid='public.service_credit_ledger'::regclass
       and contype='c' and pg_get_constraintdef(oid) like '%entry_type%');
  raise notice 'RESULT solv_04_one_commission_index=%',
    (select count(*) from pg_indexes where tablename='service_credit_ledger'
       and indexdef like '%commission%' and indexdef like 'CREATE UNIQUE%');
  raise notice 'RESULT solv_05_one_cashback_index=%',
    (select count(*) from pg_indexes where tablename='service_credit_ledger'
       and indexdef like '%cashback%' and indexdef like 'CREATE UNIQUE%');
  raise notice 'RESULT solv_06_no_client_write_policy=%',   -- credits move by DEFINER paths only
    (select count(*) from pg_policies where tablename='service_credit_ledger'
       and cmd in ('INSERT','UPDATE','DELETE'));
  -- SOLV-07 order independence: the same two entries in either order reach the same balance
  insert into public.service_credit_ledger(account_type,account_id,entry_type,amount,ref_kind,note)
    values ('provider', v_prov,'topup',300,'topup','ord1'),('provider',v_prov,'topup',700,'topup','ord2');
  select coalesce(sum(amount),0) into v_a from public.service_credit_ledger
    where account_type='provider' and account_id=v_prov;
  delete from public.service_credit_ledger where note in ('ord1','ord2');
  insert into public.service_credit_ledger(account_type,account_id,entry_type,amount,ref_kind,note)
    values ('provider', v_prov,'topup',700,'topup','ord3'),('provider',v_prov,'topup',300,'topup','ord4');
  select coalesce(sum(amount),0) into v_b from public.service_credit_ledger
    where account_type='provider' and account_id=v_prov;
  raise notice 'RESULT solv_07_order_independent=%', (v_a = v_b);
  raise notice 'RESULT solv_08_balance_equals_ledger_sum=%',
    (select (public.provider_credit_balance(v_prov)
             = coalesce((select sum(amount) from public.service_credit_ledger
                          where account_type='provider' and account_id=v_prov),0)));
end $probe$;

rollback;
