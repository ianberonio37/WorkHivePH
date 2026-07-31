-- TB-SJ12-dispute-two-personas.sql
--
-- JOURNEY SJ-J12 "dispute" — the last unwalked journey on the board (W was TODO: zero personas, zero states).
-- A dispute is the marketplace's court of last resort: it is where a buyer who has already paid says the deal
-- went wrong. Everything about it is trust-bearing, and until now nothing re-runnable asserted any of it.
--
-- THE REAL STATE MACHINE, read from the CHECK constraint rather than assumed:
--   open -> seller_responded -> admin_review -> resolved_refund | resolved_release
--
-- THE REAL AUTHORITY MODEL, read from the RLS policies:
--   insert  opened_by IN auth_worker_names()                      — you may only open a dispute AS YOURSELF
--   read    opener OR seller OR is_marketplace_admin()            — the three parties, nobody else
--   update  opener OR seller OR is_marketplace_admin()
-- `auth_worker_names()` maps auth.uid() through hive_members/marketplace_sellers, so a worker_name is a
-- CLAIM until that mapping proves it ([[feedback_free_text_identity_is_a_claim]]).
--
-- TWO PERSONAS, each acting as themselves (a persona walk that does not adopt the identity is not a walk —
-- both the read policy and the insert check are auth.uid()-scoped, so a probe with no JWT proves nothing):
--   P-buyer  opens the dispute and must NOT be able to open one in someone else's name
--   P-admin  resolves it, which is the founder-console half of this journey
-- TWO STATES: S-open (freshly opened, awaiting) and S-resolved (an admin decision recorded).
--
-- The stranger case is the one that matters most: a dispute names who paid whom and why a deal soured. If an
-- unrelated worker can read it, the marketplace leaks its most sensitive record.
--
-- ROLE, NOT JUST CLAIMS. Every assertion here is about RLS, and `postgres` is the table OWNER, who BYPASSES
-- RLS entirely. Setting only the JWT claims made the first run report three spectacular "findings" — a
-- forged dispute accepted, a stranger reading it, a stranger still reading it after resolution — every one
-- of them my instrument rather than the product ([[feedback_verify_the_instrument_before_the_page]]). The
-- sibling probes in this bank get away with claims alone because they assert TRIGGER behaviour, and triggers
-- DO fire for the owner. RLS does not. So each persona also assumes the `authenticated` role.
begin;

insert into auth.users(id, email) values
  ('5b000000-0000-4000-8000-00000000000a','tb-sj12-buyer@gate.local'),
  ('5b000000-0000-4000-8000-00000000000b','tb-sj12-seller@gate.local'),
  ('5b000000-0000-4000-8000-00000000000c','tb-sj12-admin@gate.local'),
  ('5b000000-0000-4000-8000-00000000000d','tb-sj12-stranger@gate.local');

-- Identities resolve through marketplace_sellers (one of auth_worker_names()' two sources).
insert into public.marketplace_sellers(id, worker_name, auth_uid, tier, kyb_verified, cert_verified, total_sales, rating_count) values
  ('5b000000-0000-4000-8000-0000000000f1','TB SJ12 Buyer',   '5b000000-0000-4000-8000-00000000000a','bronze',false,false,0,0),
  ('5b000000-0000-4000-8000-0000000000f2','TB SJ12 Seller',  '5b000000-0000-4000-8000-00000000000b','bronze',false,false,0,0),
  ('5b000000-0000-4000-8000-0000000000f3','TB SJ12 Admin',   '5b000000-0000-4000-8000-00000000000c','bronze',false,false,0,0),
  ('5b000000-0000-4000-8000-0000000000f4','TB SJ12 Stranger','5b000000-0000-4000-8000-00000000000d','bronze',false,false,0,0);

insert into public.marketplace_platform_admins(worker_name, granted_by) values ('TB SJ12 Admin','tb-fixture');

do $probe$
declare
  n int; v_seen int; v_status text;
  BUYER    constant text := '{"sub":"5b000000-0000-4000-8000-00000000000a","role":"authenticated"}';
  SELLER   constant text := '{"sub":"5b000000-0000-4000-8000-00000000000b","role":"authenticated"}';
  ADMIN    constant text := '{"sub":"5b000000-0000-4000-8000-00000000000c","role":"authenticated"}';
  STRANGER constant text := '{"sub":"5b000000-0000-4000-8000-00000000000d","role":"authenticated"}';
begin
  -- ── S-OPEN, as the BUYER ────────────────────────────────────────────────────────────────────────────
  perform set_config('request.jwt.claims', BUYER, true); set local role authenticated;
  begin
    insert into public.marketplace_disputes(id, opened_by, seller_name, reason, description, status)
    values ('5b000000-0000-4000-8000-0000000000e1','TB SJ12 Buyer','TB SJ12 Seller',
            'item_not_as_described','Pump arrived with a cracked housing','open');
    get diagnostics n = row_count;
    raise notice 'RESULT buyer_opens_dispute=%', case when n > 0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT buyer_opens_dispute=BLOCKED %', sqlstate; end;

  -- IDENTITY IS NOT A FREE-TEXT FIELD: opening a dispute in someone ELSE'S name must be refused, or the
  -- court of last resort becomes a way to smear a competitor.
  begin
    insert into public.marketplace_disputes(id, opened_by, seller_name, reason, status)
    values ('5b000000-0000-4000-8000-0000000000e2','TB SJ12 Stranger','TB SJ12 Seller','forged','open');
    get diagnostics n = row_count;
    raise notice 'RESULT open_as_someone_else=%', case when n > 0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT open_as_someone_else=blocked'; end;

  -- ── S-OPEN, the other parties ───────────────────────────────────────────────────────────────────────
  perform set_config('request.jwt.claims', SELLER, true); set local role authenticated;
  select count(*) into v_seen from public.marketplace_disputes
   where id = '5b000000-0000-4000-8000-0000000000e1'::uuid;
  raise notice 'RESULT seller_sees_dispute=%', v_seen;

  -- THE PRIVACY HALF: a dispute names who paid whom and why a deal soured. An unrelated worker reading it
  -- would be the marketplace leaking its most sensitive record.
  perform set_config('request.jwt.claims', STRANGER, true); set local role authenticated;
  select count(*) into v_seen from public.marketplace_disputes
   where id = '5b000000-0000-4000-8000-0000000000e1'::uuid;
  raise notice 'RESULT stranger_sees_dispute=%', v_seen;

  -- ── S-RESOLVED, as the ADMIN ────────────────────────────────────────────────────────────────────────
  -- The founder-console half of this journey: the admin is the only party who can END it.
  perform set_config('request.jwt.claims', ADMIN, true); set local role authenticated;
  begin
    update public.marketplace_disputes
       set status = 'resolved_release', admin_decision = 'Housing damage predates shipping; release funds',
           admin_decided_at = now(), resolved_at = now()
     where id = '5b000000-0000-4000-8000-0000000000e1'::uuid;
    get diagnostics n = row_count;
    raise notice 'RESULT admin_resolves=%', case when n > 0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT admin_resolves=BLOCKED %', sqlstate; end;

  -- Both parties must SEE the outcome — a resolution nobody can read is not a resolution.
  perform set_config('request.jwt.claims', BUYER, true); set local role authenticated;
  select status into v_status from public.marketplace_disputes
   where id = '5b000000-0000-4000-8000-0000000000e1'::uuid;
  raise notice 'RESULT buyer_sees_resolution=%', coalesce(v_status, '(gone)');

  -- NON-VACUITY on the privacy claim: the stranger still cannot see it AFTER resolution either. Without
  -- this, "stranger_sees_dispute=0" could have meant the row simply was not there yet.
  perform set_config('request.jwt.claims', STRANGER, true); set local role authenticated;
  select count(*) into v_seen from public.marketplace_disputes
   where id = '5b000000-0000-4000-8000-0000000000e1'::uuid;
  raise notice 'RESULT stranger_still_blind_after_resolve=%', v_seen;
end $probe$;

rollback;
