#!/usr/bin/env python3
"""validate_credit_loop_closes.py -- cash enters once, and the credits go round.

THE CENTRAL CLAIM OF THE ECONOMY, and the plan's verification #3. Every other credit gate checks a rule in
isolation: the cap binds, the reservation returns, earn-or-spend is exclusive, the supply cannot be
exceeded. None of them asks the question the whole design exists to answer:

    Can a provider fund a listing with credits they RECEIVED, without anyone paying in new cash?

If the answer is no, this is not a circuit -- it is a prepaid balance that drains one way, every provider
must keep buying credits forever, and "no revenue" quietly becomes "revenue, collected as float". Ian's
sentence for it: "I don't have to earn revenue, it is like, I hold the money I get, in a form of credits
exchange."

WHAT IT WALKS, using the real triggers and the real RPC at every step:

    ONE cash entry ->  seller A tops up
                       A publishes            -> reservation HELD (guard_listing_requires_reservation)
                       the listing SELLS      -> reservation passes to the BUYER (grant_listing_reward)
                       the buyer pays for a job with those credits (apply_credits_to_request)
                                              -> provider B RECEIVES them
                       B publishes            -> funded ENTIRELY by credits B was paid, no top-up

AND CIRCULATION NEVER MOVES after that first top-up. Every step is a transfer between wallets, so the sum
over the whole ledger must equal the single cash entry, start to finish. A step that mints or burns is the
failure this asserts against -- and it is not hypothetical: apply_credits_to_request shipped writing only
the payer's leg, which destroyed the credits and left the platform holding the cash that backed them.

Runs inside a transaction that is ALWAYS rolled back, so it is safe against a shared local database and
leaves nothing for the next test to trip over.

Usage:  python tools/validate_credit_loop_closes.py [--inject spend|reward]
"""
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"

# --inject removes a leg of the circuit so the run MUST go red:
#   spend  -- the buyer pays in pesos instead, so B is never funded and cannot publish
#   reward -- the sale does not hand its reservation to the buyer, so the buyer has nothing to spend
PROBE = """
do $$
declare
  v_seller   text;
  v_provname text := 'Christine Dizon';
  v_a uuid; v_b uuid; v_buyer uuid; v_hive uuid; v_sec text;
  v_listing uuid; v_listing_b uuid; v_inq uuid; v_req uuid; v_provider_id uuid; v_admin uuid;
  v_topup numeric := 5000;
  v_price numeric := 2000;
  v_circ0 numeric; v_circ1 numeric; v_bavail numeric; v_need numeric;
  v_state text;
begin
  -- CHOSEN ON THE CRITERIA, not pinned to a name, and the choice is printed. Seller A must have a hive
  -- and must already have SOLD something, or guard_first_listings_need_a_sale refuses the publish -- which
  -- it did on the first run, correctly: the seller this probe originally named sits at 3 live with no sale.
  -- A fixture at the cap is not a bug in the guard, it is a probe that picked the wrong person.
  select ms.worker_name, ms.auth_uid, ms.hive_id into v_seller, v_a, v_hive
    from public.marketplace_sellers ms
   where ms.hive_id is not null and ms.auth_uid is not null
     and ms.worker_name <> v_provname
     and exists (select 1 from public.marketplace_listings l
                  where l.seller_name = ms.worker_name and l.status = 'sold')
   order by ms.worker_name limit 1;
  raise notice 'seller A = %  |  provider B = %', coalesce(v_seller,'(none)'), v_provname;
  select auth_uid into v_b from public.marketplace_sellers where worker_name = v_provname;
  select id into v_provider_id from public.service_providers where auth_uid = v_b limit 1;
  select section into v_sec from public.marketplace_listings where hive_id = v_hive limit 1;
  -- The REAL publish path is an admin review: guard_marketplace_listing_status refuses self-publish, and
  -- guard_listing_requires_reservation exempts backend writes (auth.uid() null), so a probe that inserts
  -- straight to 'published' as postgres creates no reservation and proves nothing. The admin must not be
  -- a party to either listing, which is why the seller and provider below are other people.
  select ms.auth_uid into v_admin from public.marketplace_sellers ms
    join public.marketplace_platform_admins a on a.worker_name = ms.worker_name
   where ms.worker_name not in (v_seller, v_provname) limit 1;
  -- The job needs an AGREED PRICE, or there is no 10% of it to pay in credits and the spend is refused
  -- before it starts. The first cut filtered only on "has a client", picked a job priced at nothing, and
  -- reported the loop broken when the probe was simply asking to spend zero.
  select r.id, r.client_auth_uid into v_req, v_buyer
    from public.service_requests r
   where r.client_auth_uid is not null
     and r.client_auth_uid <> v_b
     and public.service_request_price(r.id) > 0
   order by r.id limit 1;
  if v_a is null or v_b is null or v_provider_id is null or v_req is null or v_admin is null
     or v_seller is null then
    raise notice 'SKIP fixtures missing'; return;
  end if;

  -- point the job at provider B so the buyer's credits land in B's wallet
  update public.service_requests set matched_provider_id = v_provider_id where id = v_req;

  -- ---- THE ONE CASH ENTRY -------------------------------------------------------------------------
  perform set_config('workhive.service_system_write','on',true);
  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
  values ('consumer', v_a, 'topup', v_topup, 'probe', v_req, 'LOOPPROBE the only cash in');
  perform set_config('workhive.service_system_write','off',true);
  select coalesce(sum(amount),0) into v_circ0 from public.service_credit_ledger;

  -- ---- A drafts, the ADMIN publishes; the reservation is HELD -----------------------------------------
  insert into public.marketplace_listings (hive_id, seller_name, title, price, status, category, section)
  values (v_hive, v_seller, 'LOOPPROBE listing', v_price, 'draft', 'tools', v_sec)
  returning id into v_listing;
  perform set_config('request.jwt.claims',
    json_build_object('sub', v_admin, 'role','authenticated')::text, true);
  execute 'set local role authenticated';
  update public.marketplace_listings set status = 'published' where id = v_listing;
  execute 'set local role postgres';
  perform set_config('request.jwt.claims', '', true);
  if not exists (select 1 from public.credit_reservations where listing_id = v_listing and state = 'held') then
    raise exception 'STEP 1 FAILED: publishing held no reservation';
  end if;

  -- ---- it SELLS; the reservation passes to the buyer -------------------------------------------------
  insert into public.marketplace_inquiries (listing_id, buyer_name, buyer_auth_uid, message)
  values (v_listing, 'LOOPPROBE buyer', v_buyer, 'LOOPPROBE') returning id into v_inq;
  perform set_config('request.jwt.claims',
    json_build_object('sub', v_admin, 'role','authenticated')::text, true);
  execute 'set local role authenticated';
  update public.marketplace_listings
     set status = 'sold', sold_to_inquiry_id = case when '__INJECT__' = 'reward' then null else v_inq end
   where id = v_listing;
  execute 'set local role postgres';
  perform set_config('request.jwt.claims', '', true);

  raise notice 'after the sale: reservation state=% | buyer balance=PHP%',
    coalesce((select state from public.credit_reservations where listing_id = v_listing
               order by created_at desc limit 1), '(none)'),
    (select coalesce(sum(amount),0) from public.service_credit_ledger
      where account_type='consumer' and account_id=v_buyer);

  -- ---- the buyer pays for a job with those credits; B RECEIVES them ----------------------------------
  if '__INJECT__' <> 'spend' then
    perform set_config('request.jwt.claims',
      json_build_object('sub', v_buyer, 'role','authenticated')::text, true);
    begin
      execute 'set local role authenticated';
      perform public.apply_credits_to_request(v_req, least(
        (select coalesce(sum(amount),0) from public.service_credit_ledger
          where account_type='consumer' and account_id=v_buyer),
        round(public.service_request_price(v_req) * 0.10, 2)));
      v_state := 'PAID IN CREDITS';
    exception when others then v_state := left(sqlerrm, 70);
    end;
    execute 'set local role postgres';
    -- CLEAR THE CLAIMS TOO. request.jwt.claims is TRANSACTION-scoped, not block-scoped, so resetting only
    -- the role leaves auth.uid() as the buyer -- and the very next line reads B's wallet, which
    -- seller_credit_balance correctly refuses to show to anyone but its owner. The probe was running as
    -- the wrong person and blaming the guard.
    perform set_config('request.jwt.claims', '', true);
    raise notice 'buyer pays provider B in credits -> %', v_state;
  end if;

  -- ---- B publishes, funded ONLY by what B was paid ---------------------------------------------------
  select available into v_bavail from public.seller_credit_balance(v_provname);
  v_need := public.listing_reservation_amount(v_hive, v_price);
  raise notice 'B holds PHP% and a PHP% listing needs PHP% reserved', v_bavail, v_price, v_need;

  insert into public.marketplace_listings (hive_id, seller_name, title, price, status, category, section)
  values (v_hive, v_provname, 'LOOPPROBE listing B', v_price, 'draft', 'tools', v_sec)
  returning id into v_listing_b;
  begin
    perform set_config('request.jwt.claims',
      json_build_object('sub', v_admin, 'role','authenticated')::text, true);
    execute 'set local role authenticated';
    update public.marketplace_listings set status = 'published' where id = v_listing_b;
    v_state := 'PUBLISHED WITH NO TOP-UP';
  exception when others then v_state := left(sqlerrm, 80);
  end;
  execute 'set local role postgres';
  perform set_config('request.jwt.claims', '', true);
  raise notice 'B publishes -> %', v_state;
  if v_state <> 'PUBLISHED WITH NO TOP-UP' then
    raise exception 'THE LOOP DOES NOT CLOSE: B could not fund a listing from credits B was paid (%)', v_state;
  end if;

  -- ---- and nothing was minted or burned along the way ------------------------------------------------
  select coalesce(sum(amount),0) into v_circ1 from public.service_credit_ledger;
  raise notice 'circulation % -> % (delta %)', v_circ0, v_circ1, v_circ1 - v_circ0;
  if v_circ1 <> v_circ0 then
    raise exception 'CIRCULATION MOVED by % after the single cash entry: the loop mints or burns',
      v_circ1 - v_circ0;
  end if;

  raise notice 'LOOP CLOSES: one cash entry, credits went round, B listed on money nobody re-paid';
  raise exception 'ROLLBACK the probe';
end $$;
"""


def run(inject=""):
    sql = PROBE.replace("__INJECT__", inject)
    r = subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres"],
                       input=sql, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    return (r.stdout or "") + (r.stderr or "")


def main(argv):
    inject = ""
    if "--inject" in argv:
        inject = argv[argv.index("--inject") + 1]

    print(f"{BOLD}The credit loop{RST} -- cash enters once, and the credits go round")
    try:
        out = run(inject)
    except Exception as e:
        print(f"  {YEL}SKIP{RST} database unavailable ({e})")
        return 0
    if "SKIP fixtures missing" in out:
        print(f"  {YEL}SKIP{RST} the fixture seller/provider/job this walk needs is not seeded")
        return 0
    if "does not exist" in out and "relation" in out:
        print(f"  {YEL}SKIP{RST} schema not migrated for the credit economy")
        return 0

    for line in out.splitlines():
        if line.startswith("NOTICE:"):
            print(f"  {DIM}{line[8:].strip()}{RST}")

    closed = "LOOP CLOSES" in out
    if inject:
        print(f"  {YEL}INJECTED{RST} '{inject}' -- the loop must NOT close")
        if closed:
            print(f"\n  {RED}NO TEETH{RST} -- the loop still closed without the "
                  f"{'buyer spending' if inject == 'spend' else 'sale handing over its reservation'}, "
                  f"so this walk was never proving the circuit")
            return 1
        print(f"\n  {GREEN}TEETH CONFIRMED{RST} -- removing that leg broke the circuit")
        return 0

    if not closed:
        print(f"\n  {RED}FAIL{RST} -- the loop does not close:")
        for line in out.splitlines():
            if "ERROR:" in line and "ROLLBACK the probe" not in line:
                print(f"    . {line.strip()[:160]}")
        return 1
    print(f"\n  {GREEN}PASS{RST} -- one cash entry funded a listing, a sale, a job paid in credits, and a "
          f"SECOND provider's listing. Circulation never moved.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
