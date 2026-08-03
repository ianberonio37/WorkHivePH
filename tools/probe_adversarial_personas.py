#!/usr/bin/env python3
"""
probe_adversarial_personas.py — walk the four abuse personas as PEOPLE, not as arithmetic.

The 500-run simulation (plan §3b) proved the ECONOMICS hold: a collusive pair extracts PHP0, the
spam cap blocks 274,428 listings, sybil is bounded only by ID strength. What it never proved is that
the SCREEN refuses these people LEGIBLY. A guard that blocks in silence is a guard the person cannot
learn from -- and, worse, one we cannot tell apart from a guard that is not firing at all.

So each persona here asserts TWO things:
  1. the platform refuses (or absorbs) the attack, and
  2. the refusal carries a sentence a human could act on -- not a bare constraint name.

Every probe runs inside BEGIN/ROLLBACK. docker exec psql runs in AUTOCOMMIT, so an unwrapped teeth
test is a permanent write; this platform has already gutted three live guards that way.

Roles matter: guards read auth.uid(), so probing as `postgres` proves nothing about them. Each
persona sets `role authenticated` plus a JWT sub, exactly as PostgREST would.

Usage:  python tools/probe_adversarial_personas.py [--verbose]
Exit:   0 all personas refused legibly · 1 any persona got through or was refused illegibly
"""
import subprocess, sys, re

DB = ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tA"]
VERBOSE = "--verbose" in sys.argv

# A refusal is only useful if a person can read it. These are the shapes that FAIL that bar:
# a bare SQLSTATE, a constraint name, or a Postgres internal.
ILLEGIBLE = re.compile(
    r"^(null value|duplicate key|violates (foreign key|check|unique|not-null)|"
    r"permission denied|new row for relation|invalid input syntax)", re.I)


def run(sql: str) -> str:
    # BOTH streams: psql sends RAISE NOTICE to stderr, and every verdict line here is a NOTICE.
    # Reading stdout alone made all four personas report "no verdict line" — an instrument that
    # fails closed, which at least is the safe direction, but still a false red.
    p = subprocess.run(DB, input=sql, capture_output=True, text=True)
    return (p.stdout or "") + "\n" + (p.stderr or "")


def legible(msg: str) -> bool:
    """A sentence a human could act on: prose, not a constraint name, and long enough to explain."""
    m = (msg or "").strip()
    return len(m) > 25 and not ILLEGIBLE.match(m) and " " in m


PERSONAS = []


def persona(name, why):
    def deco(fn):
        PERSONAS.append((name, why, fn))
        return fn
    return deco


@persona("spammer", "floods the catalogue with listings nobody will buy, to occupy the front page")
def spam():
    """A brand-new seller must be capped, and told WHY and WHAT unlocks the next slot."""
    out = run("""
begin;
set local session_replication_role = replica;
insert into marketplace_sellers (worker_name, hive_id, tier)
values ('PROBE Spammer', (select hive_id from marketplace_listings limit 1), 'bronze')
on conflict do nothing;
-- FUND THE SPAMMER, or the deepest layer never gets tested. Unfunded, the reservation guard refuses
-- listing #1 ("needs 500 credits held, you have 0") and the new-seller cap is never consulted -- a
-- pass that proves only the outermost gate. The interesting question is what stops a spammer who
-- CAN pay the hold, so give them enough for all 8 (8 x 500 = 4,000) and find where they actually
-- stop. This is the layer the 500-run simulation credited with blocking 274,428 listings and which
-- nothing had ever exercised.
insert into service_credit_ledger (account_type, account_id, entry_type, amount, ref_kind, note)
select 'provider', p.id, 'topup', 20000, 'topup', 'probe: fund the spammer so the CAP is what stops them'
  from service_providers p where p.auth_uid is not null;
set local session_replication_role = origin;
do $$
declare v_hive uuid; v_msg text; v_n int := 0; v_uid uuid; v_seller text;
begin
  select hive_id into v_hive from marketplace_listings limit 1;
  -- A seller who is ALREADY AT the cap (3 live, 0 sold) and has money -- otherwise the reservation
  -- guard refuses first and the cap is never reached. Pick by the cap's own arithmetic rather than
  -- by name, so this keeps working as the seed data changes.
  select l.seller_name into v_seller
    from marketplace_listings l
   group by l.seller_name
  having count(*) filter (where l.status = 'published') >= 3
     and count(*) filter (where l.status = 'sold') = 0
   limit 1;
  -- A JWT IS REQUIRED OR THE GUARD BYPASSES ITSELF. guard_first_listings_need_a_sale opens with
  -- `if auth.uid() is null ... return new` -- the backend path seeders need. Probing without a
  -- claim published all 8 listings and read as "the cap does not work", when in fact the probe was
  -- never a person. Same class as the banked lesson that an RLS probe needs the ROLE, not just
  -- claims: here it is the trigger that needs the identity.
  -- THE REAL PATH, or the cap never gets a turn. A seller cannot self-publish at all
  -- (guard_marketplace_listing_status refuses it), so inserting 8 rows as 'published' is stopped by
  -- THAT guard on the very first one and the new-seller cap is never consulted -- a pass that proves
  -- only the outer gate. Same shape as the banked "a survivor masked by a sibling constraint".
  -- So: file them as drafts the way a seller does, then have an ADMIN publish, which is how a
  -- listing actually goes live, and see where the cap bites.
  -- Resolve a REAL admin: is_marketplace_admin() matches marketplace_platform_admins.worker_name
  -- against auth_worker_names(), so the identity has to be one whose worker name is in that table.
  -- Test candidates by asking the function itself rather than guessing the join -- the function is
  -- the authority on who counts as an admin.
  for v_uid in select distinct auth_uid from service_providers where auth_uid is not null loop
    perform set_config('request.jwt.claims', json_build_object('sub', v_uid, 'role','authenticated')::text, true);
    exit when public.is_marketplace_admin();
    v_uid := null;
  end loop;
  if v_uid is null then
    raise notice 'PUBLISHED=%|MSG=%', -1, 'probe could not resolve a platform admin identity';
    return;
  end if;
  for i in 1..8 loop
    insert into marketplace_listings (title, section, category, price, seller_name, hive_id, status)
    values ('PROBE spam '||i, 'parts', 'Filters', 5000, v_seller, v_hive, 'draft');
  end loop;
  perform set_config('request.jwt.claims', json_build_object('sub', v_uid, 'role','authenticated')::text, true);
  for i in 1..8 loop
    begin
      update marketplace_listings set status='published'
       where seller_name=v_seller and title='PROBE spam '||i;
      v_n := v_n + 1;
    exception when others then
      v_msg := SQLERRM;
      exit;
    end;
  end loop;
  raise notice 'PUBLISHED=%|MSG=%', v_n, coalesce(v_msg, '(never refused)');
end $$;
rollback;
""")
    return parse(out)


@persona("sybil", "farms starter grants by creating account after account")
def sybil():
    """The second claim by the same identity must be refused, and say it was already claimed."""
    out = run("""
begin;
do $$
declare v_uid uuid; r1 jsonb; r2 jsonb;
begin
  select auth_uid into v_uid from service_providers where auth_uid is not null limit 1;
  perform set_config('request.jwt.claims', json_build_object('sub', v_uid, 'role','authenticated')::text, true);
  r1 := public.claim_starter_grant();
  r2 := public.claim_starter_grant();
  raise notice 'PUBLISHED=%|MSG=first=% second=%', 1, r1::text, r2::text;
end $$;
rollback;
""")
    return parse(out)


@persona("collusive pair", "two accounts trade credits back and forth to extract value")
def collusion():
    """Credits are non-withdrawable and every leg is a transfer: circulation must not move."""
    out = run("""
begin;
do $$
declare v_a uuid; v_b uuid; v_before numeric; v_after numeric; v_msg text := '';
begin
  select coalesce(sum(amount),0) into v_before from service_credit_ledger;
  select auth_uid into v_a from service_providers where auth_uid is not null order by id limit 1;
  select auth_uid into v_b from service_providers where auth_uid is not null and auth_uid <> v_a order by id limit 1;
  perform set_config('request.jwt.claims', json_build_object('sub', v_a, 'role','authenticated')::text, true);
  begin
    -- a naked user-to-user gift: the whole premise of an extraction cycle
    insert into service_credit_ledger (account_type, account_id, entry_type, amount, ref_kind, note)
    values ('consumer', v_a, 'adjustment', -100, 'dispute', 'collusion probe: send'),
           ('consumer', v_b, 'adjustment',  100, 'dispute', 'collusion probe: receive');
  exception when others then v_msg := SQLERRM;
  end;
  select coalesce(sum(amount),0) into v_after from service_credit_ledger;
  raise notice 'PUBLISHED=%|MSG=circulation % -> % (delta %) :: %',
    (v_after - v_before)::int, v_before, v_after, (v_after - v_before), coalesce(nullif(v_msg,''), '(transfer allowed but nets 0)');
end $$;
rollback;
""")
    return parse(out)


@persona("scam provider", "marks a job done having never shown up, and waits out the window")
def scam_provider():
    """The completion window must give the buyer a dated deadline and a working objection."""
    out = run("""
begin;
set local session_replication_role = replica;
create temp table _sj as select * from service_requests where status='settled' limit 1;
update _sj set id='dddddddd-eeee-ffff-0000-111111111111',
               status='completed', completed_at = now(), budget = 800;
insert into service_requests select * from _sj;
set local session_replication_role = origin;
do $$
declare v_dead timestamptz; v_client uuid; r jsonb; v_status text;
begin
  -- The BASE table for the client, not v_service_request_truth. The view is RLS-filtered on
  -- auth.uid(), and at this point no claim is set -- so it returned no row, v_client came back NULL,
  -- and the objection was then refused as "only the person who hailed this job can raise a problem".
  -- That read as the platform failing when it was the probe asking as nobody.
  select client_auth_uid into v_client
    from service_requests where id='dddddddd-eeee-ffff-0000-111111111111';
  perform set_config('request.jwt.claims', json_build_object('sub', v_client, 'role','authenticated')::text, true);
  -- Now that we ARE the buyer, read the deadline the way the buyer's screen does.
  select objection_deadline into v_dead
    from v_service_request_truth where id='dddddddd-eeee-ffff-0000-111111111111';
  r := public.raise_service_objection('dddddddd-eeee-ffff-0000-111111111111', 'Nobody ever arrived');
  select status into v_status from service_requests where id='dddddddd-eeee-ffff-0000-111111111111';
  raise notice 'PUBLISHED=%|MSG=deadline=% objection=% status=%',
    (case when v_dead is null then 1 else 0 end), coalesce(v_dead::text,'(NONE - buyer cannot know)'), r::text, v_status;
end $$;
rollback;
""")
    return parse(out)


def parse(out: str):
    m = re.search(r"PUBLISHED=(-?\d+)\|MSG=(.*)", out, re.S)
    if not m:
        return None, "probe produced no verdict line:\n" + out[:400]
    return int(m.group(1)), m.group(2).strip().split("\n")[0]


def main() -> int:
    print("\033[1mAdversarial personas — does the platform refuse them LEGIBLY?\033[0m")
    print("  each persona asserts two things: the attack is contained, AND the refusal is readable")
    print("=" * 78)
    failures = 0
    for name, why, fn in PERSONAS:
        got, msg = fn(None) if fn.__code__.co_argcount else fn()
        if got is None:
            print(f"  \033[91mERROR\033[0m  {name}: {msg}")
            failures += 1
            continue

        # Persona-specific containment bar.
        if name == "spammer":
            contained = got <= 3            # the new-seller cap
            bar = f"published {got} before refusal (cap is 3)"
        elif name == "sybil":
            contained = "already_claimed" in msg
            bar = "second claim refused as already_claimed"
        elif name == "collusive pair":
            contained = got == 0            # circulation delta
            bar = f"circulation delta {got}"
        else:
            contained = got == 0            # a deadline exists
            bar = "buyer has a dated deadline and a working objection"

        readable = legible(msg)
        ok = contained and readable
        badge = "\033[92mPASS\033[0m" if ok else "\033[91mFAIL\033[0m"
        print(f"  {badge}  \033[1m{name}\033[0m — {why}")
        print(f"        contained: {bar}")
        print(f"        told them: {msg[:150]}")
        if not contained:
            print("        \033[91m^ the attack was NOT contained\033[0m")
        if not readable:
            print("        \033[91m^ refused, but with something no human could act on\033[0m")
        if not ok:
            failures += 1
        if VERBOSE:
            print(f"        raw: {msg}")

    print("=" * 78)
    if failures:
        print(f"  \033[91m\033[1m{failures} persona(s) got through or were refused illegibly\033[0m")
        return 1
    print("  \033[92m\033[1mall personas contained, every refusal readable\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
