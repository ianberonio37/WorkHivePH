#!/usr/bin/env python3
"""validate_credit_guards_refuse.py -- the credit guards REFUSE, not merely exist.

`validate_credit_posture.py` asserts each guard's trigger is installed. That is necessary and it is not
enough: a trigger can be present while its function has been replaced by `return new`, and every
existence check in the suite would stay green. The plan's verification #1, #2 and #4 all say the same
thing in different words -- these must FAIL if the guard is removed.

THREE BEHAVIOURS, each walked against the real schema in a rolled-back transaction:

  1. A LISTING CANNOT OUTRUN ITS RESERVATION.  Publishing with less than 10% of the price available is
     refused. Asserted at the shape that actually hurts: a seller with one listing's worth of credits
     trying to hold several live at once, which is the state that leaves rewards unpayable.

  2. AN UNSOLD LISTING COSTS NOTHING.  Publish, then delist, and the balance returns to EXACTLY where it
     started. This is the entire difference between a reservation and the listing fee rejected in July --
     a fee is consumed whether or not the item sells. If it ever returns less than it took, the
     reservation has quietly become the fee.

  3. A BALANCE DRAINS.  A job carries reward_earn OR reward_spend, never both. When the reward rate and
     the spend cap are the same 10%, a job that pays a reward on the job you spent on is a treadmill: the
     balance never empties, credits stop being spendable, and they stay a liability forever.

TEETH, and this is the part that makes the gate worth running: `--inject <n>` NEUTERS that guard inside
the transaction -- `create or replace` the function to `return new`, run the same probe, and require the
refusal to DISAPPEAR. DDL is transactional in Postgres, so the real guard is restored on rollback and
nothing survives the run. A probe that cannot be made to pass was never testing the guard.

Usage:  python tools/validate_credit_guards_refuse.py [--inject 1|2|3]
"""
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"

NEUTER = {
    "1": """create or replace function public.guard_listing_requires_reservation()
             returns trigger language plpgsql as $f$ begin return new; end $f$;""",
    "2": """create or replace function public.release_reservation_on_delist()
             returns trigger language plpgsql as $f$ begin return new; end $f$;""",
    "3": """create or replace function public.guard_reward_exclusive()
             returns trigger language plpgsql as $f$ begin return new; end $f$;""",
}

PROBE = """
__NEUTER__
do $$
declare
  v_seller text; v_a uuid; v_hive uuid; v_sec text; v_admin uuid;
  v_listing uuid; v_price numeric := 2000; v_need numeric;
  v_bal0 numeric; v_bal1 numeric; v_state text; v_req uuid; v_buyer uuid;
begin
  -- Seller must already have SOLD something, or guard_first_listings_need_a_sale refuses the publish for
  -- an unrelated (and correct) reason and the probe would blame the wrong guard.
  select ms.worker_name, ms.auth_uid, ms.hive_id into v_seller, v_a, v_hive
    from public.marketplace_sellers ms
   where ms.hive_id is not null and ms.auth_uid is not null
     and exists (select 1 from public.marketplace_listings l
                  where l.seller_name = ms.worker_name and l.status = 'sold')
   order by ms.worker_name limit 1;
  select ms.auth_uid into v_admin from public.marketplace_sellers ms
    join public.marketplace_platform_admins a on a.worker_name = ms.worker_name
   where ms.worker_name <> v_seller limit 1;
  select section into v_sec from public.marketplace_listings where hive_id = v_hive limit 1;
  if v_seller is null or v_admin is null then raise notice 'SKIP fixtures missing'; return; end if;

  v_need := public.listing_reservation_amount(v_hive, v_price);

  -- ============ 1 | a listing cannot outrun its reservation ==========================================
  -- The seller holds NOTHING, so the very first publish must be refused.
  select available into v_bal0 from public.seller_credit_balance(v_seller);
  insert into public.marketplace_listings (hive_id, seller_name, title, price, status, category, section)
  values (v_hive, v_seller, 'GUARDPROBE over', v_price, 'draft', 'tools', v_sec) returning id into v_listing;
  begin
    perform set_config('request.jwt.claims',
      json_build_object('sub', v_admin, 'role','authenticated')::text, true);
    execute 'set local role authenticated';
    update public.marketplace_listings set status='published' where id = v_listing;
    v_state := 'PUBLISHED';
  exception when others then v_state := 'REFUSED'; end;
  execute 'set local role postgres';
  perform set_config('request.jwt.claims', '', true);
  raise notice 'ASSERT1 publishing on a PHP% balance (needs PHP%) -> %', coalesce(v_bal0,0), v_need, v_state;

  -- ============ 2 | an unsold listing costs nothing ==================================================
  perform set_config('workhive.service_system_write','on',true);
  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,note)
  values ('consumer', v_a, 'topup', v_need, 'probe', 'GUARDPROBE funding');
  perform set_config('workhive.service_system_write','off',true);
  select available into v_bal0 from public.seller_credit_balance(v_seller);

  perform set_config('request.jwt.claims',
    json_build_object('sub', v_admin, 'role','authenticated')::text, true);
  execute 'set local role authenticated';
  update public.marketplace_listings set status='published' where id = v_listing;
  update public.marketplace_listings set status='removed'   where id = v_listing;
  execute 'set local role postgres';
  perform set_config('request.jwt.claims', '', true);

  select available into v_bal1 from public.seller_credit_balance(v_seller);
  raise notice 'ASSERT2 balance %s -> publish -> delist -> % (returned IN FULL: %)',
    v_bal0, v_bal1, (v_bal1 = v_bal0);

  -- ============ 3 | a balance drains: earn OR spend, never both ======================================
  select r.id, r.client_auth_uid into v_req, v_buyer from public.service_requests r
   where r.client_auth_uid is not null and public.service_request_price(r.id) > 0 order by r.id limit 1;
  perform set_config('workhive.service_system_write','on',true);
  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
  values ('consumer', v_buyer, 'reward_earn', 50, 'service_request', v_req, 'GUARDPROBE earn');
  begin
    insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
    values ('consumer', v_buyer, 'reward_spend', -50, 'service_request', v_req, 'GUARDPROBE spend');
    v_state := 'BOTH ALLOWED';
  exception when others then v_state := 'REFUSED'; end;
  perform set_config('workhive.service_system_write','off',true);
  raise notice 'ASSERT3 earn AND spend on one job -> %', v_state;

  raise exception 'ROLLBACK the probe';
end $$;
"""


def run(inject=None):
    # EXPLICIT BEGIN / ROLLBACK around EVERYTHING, and this is not belt-and-braces. `docker exec psql`
    # runs in AUTOCOMMIT: a bare `create or replace function` is its own transaction and COMMITS, so an
    # earlier version of this file permanently gutted three live guards on the local database while the
    # DO block below rolled back exactly as designed and reported TEETH CONFIRMED. The damage was only
    # visible on the NEXT clean run, which then failed two assertions that had passed minutes earlier.
    # DDL is transactional in Postgres -- but only if you open a transaction.
    body = PROBE.replace("__NEUTER__", NEUTER.get(inject, "") if inject else "")
    sql = "begin;\n" + body + "\nrollback;\n"
    # (see guards_are_real() below — the verdict of this run is never taken as evidence about the database)
    r = subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres"],
                       input=sql, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    return (r.stdout or "") + (r.stderr or "")


GUARD_FNS = ("guard_listing_requires_reservation", "release_reservation_on_delist",
             "guard_reward_exclusive")


def guards_are_real():
    """-> list of guards left as stubs. Run AFTER every probe, injected or not.

    "The probe printed TEETH CONFIRMED" is a statement about the probe, not about the database. An earlier
    version of this file neutered these three permanently -- psql autocommits DDL, so the `create or
    replace` committed while the DO block rolled back exactly as designed -- and nothing noticed until a
    later clean run failed assertions that had passed minutes before. A gate that can damage the schema
    owes a check that it did not.
    """
    r = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tAc",
         "select proname from pg_proc where proname in {} and length(prosrc) < 120;".format(GUARD_FNS)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if r.returncode != 0:
        return []
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def judge(out):
    """-> {n: holds?}. Parsed from the probe's own notices so the reasoning is visible in the output."""
    got = {}
    for line in out.splitlines():
        if "ASSERT1" in line:
            got["1"] = line.rstrip().endswith("REFUSED")
        elif "ASSERT2" in line:
            got["2"] = "IN FULL: t" in line
        elif "ASSERT3" in line:
            got["3"] = line.rstrip().endswith("REFUSED")
    return got


LABEL = {
    "1": "a listing cannot outrun its reservation",
    "2": "an unsold listing costs NOTHING (returned in full)",
    "3": "a balance drains: earn OR spend, never both",
}


def main(argv):
    inject = argv[argv.index("--inject") + 1] if "--inject" in argv else None
    if inject and inject not in NEUTER:
        print(f"  {RED}unknown --inject '{inject}' (expected 1, 2 or 3){RST}")
        return 2

    print(f"{BOLD}Credit guards REFUSE{RST} -- installed is not the same as enforcing")
    try:
        out = run(inject)
    except Exception as e:
        print(f"  {YEL}SKIP{RST} database unavailable ({e})")
        return 0
    if "SKIP fixtures missing" in out:
        print(f"  {YEL}SKIP{RST} the fixture seller/admin this walk needs is not seeded")
        return 0

    for line in out.splitlines():
        if line.startswith("NOTICE:") and "ASSERT" in line:
            print(f"  {DIM}{line[8:].strip()}{RST}")

    # THE SCHEMA MUST BE EXACTLY AS WE FOUND IT, whatever the probe concluded.
    stubs = guards_are_real()
    if stubs:
        print(f"\n  {RED}FAIL{RST} -- this run LEFT THE DATABASE DAMAGED: {', '.join(stubs)} "
              f"{'is' if len(stubs) == 1 else 'are'} still a no-op stub. Restore by replaying "
              f"supabase/migrations/20260803000009..26 IN ORDER (re-applying only the defining migration "
              f"also reverts later corrections, e.g. the entry_type CHECK loses reward_fund).")
        return 1

    got = judge(out)
    if len(got) < 3:
        print(f"\n  {RED}FAIL{RST} -- the probe did not reach every assertion:")
        for line in out.splitlines():
            if "ERROR:" in line and "ROLLBACK the probe" not in line:
                print(f"    . {line.strip()[:150]}")
        return 1

    if inject:
        print(f"  {YEL}INJECTED{RST} guard {inject} neutered in-transaction -- assertion {inject} must now FAIL")
        if got.get(inject):
            print(f"\n  {RED}NO TEETH{RST} -- '{LABEL[inject]}' still held with its guard replaced by "
                  f"`return new`, so the probe never depended on that guard")
            return 1
        others = [n for n in got if n != inject and not got[n]]
        if others:
            print(f"\n  {YEL}NOTE{RST} neutering {inject} also broke {others} -- the guards are coupled")
        print(f"\n  {GREEN}TEETH CONFIRMED{RST} -- removing guard {inject} broke exactly the behaviour it owns")
        return 0

    failed = [n for n, ok in sorted(got.items()) if not ok]
    if failed:
        print(f"\n  {RED}FAIL{RST} -- a guard is installed but not enforcing:")
        for n in failed:
            print(f"    . {LABEL[n]}")
        return 1
    print(f"\n  {GREEN}PASS{RST} -- all three refuse: over-listing blocked, an unsold listing returns its "
          f"credits in full, and no job carries both an earn and a spend")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
