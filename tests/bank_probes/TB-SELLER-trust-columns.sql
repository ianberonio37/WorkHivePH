-- TB-SELLER-trust-columns.sql
--
-- `guard_marketplace_seller_trust_columns` is the SELLER-side sibling of `guard_service_provider_writes`
-- (§12's TRUST guard). It protects the columns a marketplace SELLER must not be able to say about themselves,
-- because buyers price against them:
--
--   kyb_verified / cert_verified (+ *_at)  the platform's verification badges
--   tier                                   bronze/silver/gold — a trust ladder
--   rating_avg / rating_count              social proof, recomputed from real reviews
--   total_sales                            a track record the matcher and buyers weigh
--   response_rate / response_time_h        responsiveness signals
--
-- Found unscored: NO registered gate names it, so deleting any self-upgrade conjunct or the INSERT guard
-- would have gone unnoticed. This cell banks it (a walked probe is not a banked cell —
-- [[feedback_a_walked_cell_is_not_a_banked_cell]]).
--
-- THE ADMIN BYPASS IS INTENTIONAL (Ian, 2026-07-31). A marketplace admin who is ALSO a seller CAN set their
-- OWN trust columns. This was found live (both current admins are sellers) and RAISED as the mig-003 self-deal
-- class ([[feedback_admin_bypass_before_party_check_is_selfdeal]]); Ian decided to LEAVE IT AS-IS — an admin is
-- the platform trust authority and self-management is permitted. So this cell asserts that behaviour too, on
-- purpose: it LOCKS the decision. A future change that made the admin bypass party-guarded would flip
-- `admin_self_kyb` to blocked and turn THIS cell red, forcing the decision to be re-made rather than drifting.
--
-- THE GUARD IS ISOLATED FROM RLS. Each identity acts with its jwt claims set but as the superuser (RLS
-- bypassed), so whatever refuses is the TRIGGER, not a missing UPDATE grant. This scores the GUARD — the thing
-- the mutation harness mutates — exactly as the finding was verified. Every refusal is paired with the
-- legitimate write, so "protects the trust columns" is separated from "rejects sellers".
begin;

insert into auth.users(id, email) values
  ('be000000-0000-4000-8000-00000000000a','tb-seller-nonadmin@gate.local'),
  ('be000000-0000-4000-8000-00000000000b','tb-seller-admin@gate.local');

-- Planted as postgres (auth.uid() null -> vetted backend path), so the fixtures themselves are not under test.
-- Deliberately UNVERIFIED bronze with no sales: the honest starting state for a new seller.
insert into public.marketplace_sellers(id, worker_name, auth_uid, tier, kyb_verified, cert_verified,
       total_sales, rating_count) values
  ('be000000-0000-4000-8000-0000000000a1','TB Seller NonAdmin','be000000-0000-4000-8000-00000000000a',
   'bronze', false, false, 0, 0),
  ('be000000-0000-4000-8000-0000000000b1','TB Seller Admin','be000000-0000-4000-8000-00000000000b',
   'bronze', false, false, 0, 0),
  -- a stranger's seller row for the admin-moderates-others positive
  ('be000000-0000-4000-8000-0000000000c1','TB Seller Stranger', null,
   'bronze', false, false, 0, 0);
insert into public.marketplace_platform_admins(worker_name, granted_by)
  values ('TB Seller Admin','tb-fixture');

-- ── A NON-ADMIN SELLER CANNOT SELF-FORGE TRUST ──────────────────────────────────────────
select set_config('request.jwt.claims',
  '{"sub":"be000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);

do $probe$
declare n int; me uuid := 'be000000-0000-4000-8000-00000000000a';
begin
  -- non-vacuity: this identity must NOT be an admin, or every refusal below would be the bypass talking.
  raise notice 'RESULT nonadmin_is_not_admin=%', not public.is_marketplace_admin();

  begin update public.marketplace_sellers set kyb_verified=true where auth_uid=me;
        get diagnostics n=row_count; raise notice 'RESULT self_kyb=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT self_kyb=blocked'; end;

  -- cert_verified ALONE (not cert_verified_at): the guard pins the boolean and the timestamp on SEPARATE
  -- conjuncts, so setting both would let the timestamp pin mask a dropped boolean pin. Isolating the boolean
  -- is what gives the seller_cert_selfverify_allowed operator something to fail against.
  begin update public.marketplace_sellers set cert_verified=true where auth_uid=me;
        get diagnostics n=row_count; raise notice 'RESULT self_cert=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT self_cert=blocked'; end;

  -- cert_verified_at ALONE: the timestamp pin is a distinct rule (a badge with a forged date has forged
  -- provenance even if the boolean is honest), so it gets its own case.
  begin update public.marketplace_sellers set cert_verified_at=now() where auth_uid=me;
        get diagnostics n=row_count; raise notice 'RESULT self_cert_at=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT self_cert_at=blocked'; end;

  begin update public.marketplace_sellers set tier='gold' where auth_uid=me;
        get diagnostics n=row_count; raise notice 'RESULT self_tier=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT self_tier=blocked'; end;

  begin update public.marketplace_sellers set total_sales=999 where auth_uid=me;
        get diagnostics n=row_count; raise notice 'RESULT self_sales=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT self_sales=blocked'; end;

  -- INSERT branch: a seller may not be BORN verified.
  begin
    insert into public.marketplace_sellers(id, worker_name, auth_uid, tier, kyb_verified, cert_verified, total_sales, rating_count)
      values ('be000000-0000-4000-8000-0000000000a2','TB Seller NonAdmin Born', me, 'gold', true, true, 50, 0);
    get diagnostics n=row_count; raise notice 'RESULT born_verified=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT born_verified=blocked'; end;

  -- the legitimate write that separates "protects trust" from "rejects sellers"
  begin update public.marketplace_sellers set messenger_username='@tb' where auth_uid=me;
        get diagnostics n=row_count; raise notice 'RESULT legit_edit=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT legit_edit=BROKEN'; end;
end $probe$;

-- ── AN ADMIN-SELLER MAY SELF-MANAGE (intentional, Ian 2026-07-31) AND MODERATE OTHERS ───
select set_config('request.jwt.claims',
  '{"sub":"be000000-0000-4000-8000-00000000000b","role":"authenticated"}', true);

do $probe$
declare n int; me uuid := 'be000000-0000-4000-8000-00000000000b';
begin
  raise notice 'RESULT admin_is_admin=%', public.is_marketplace_admin();

  -- INTENTIONAL: an admin CAN set their own trust columns. Locked so removing the bypass turns this red.
  begin update public.marketplace_sellers set kyb_verified=true, tier='gold', total_sales=500 where auth_uid=me;
        get diagnostics n=row_count; raise notice 'RESULT admin_self_kyb=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT admin_self_kyb=blocked'; end;

  -- their legitimate moderator job: verify a STRANGER's seller account.
  begin update public.marketplace_sellers set kyb_verified=true where id='be000000-0000-4000-8000-0000000000c1';
        get diagnostics n=row_count; raise notice 'RESULT admin_verify_stranger=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT admin_verify_stranger=BROKEN'; end;
end $probe$;

rollback;
