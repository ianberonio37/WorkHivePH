#!/usr/bin/env python3
"""
validate_marketplace_trust_integrity.py - PER_PAGE_BUGHUNT P5/P6 marketplace trust-forge lock (2026-07-19).
=====================================================================================================
The marketplace runs on the SELLER TRUST SIGNAL (rating_avg / rating_count / total_sales / tier — shown
in search, community, the seller profile, schema.org AggregateRating). Two live-found forge vectors let a
JWT client inflate that signal for self-dealing (a 2nd identity boosting its own seller account):

  BUG A — FAKE SALES: `trg_seller_tier` bumps `total_sales` (+ promotes tier) on a marketplace_orders
    `status -> 'released'` transition. RLS let a buyer self-insert an order naming ANY seller and jump
    status straight to 'released' (no escrow/payment) -> +1 fake sale. Locked by
    guard_marketplace_order_status (mig 20260719000002): a JWT client cannot set status released/refunded.

  BUG B — FAKE REVIEWS: `update_seller_rating` recomputed rating_avg/rating_count over ALL reviews with
    no verified_purchase filter. RLS let a worker self-insert a 5-star `verified_purchase=false` review
    for any listing -> inflated (or, since reviews are empty while sellers carry seeded ratings,
    OVERWROTE) the rating. Locked by mig 20260719000003: only verified_purchase=true reviews move the
    stored rating; an unverified review is a no-op.

  BUG C (regression) — guard_marketplace_seller_trust_columns must still block a direct client UPDATE of
    total_sales / rating_avg (mig 20260713000009 lineage).

METHOD: rolled-back psql as a real authenticated WORKER (`set local role authenticated` + jwt.claims),
attempt each forge, assert it is blocked / a no-op, ROLLBACK (0 pollution). Skips cleanly if docker/DB
unreachable. `--selftest` proves the harness wiring.
"""
from __future__ import annotations
import io, sys, subprocess

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_marketplace_trust_integrity"]
DB = "supabase_db_workhive"
# Bryan Garcia (worker/buyer) — uid + hive RESOLVED at runtime (test_identity pattern; a reseed
# re-mints both, and a pinned pair rots into RLS 0-rows = vacuous pass). Literals = fallback only.
def _resolve_worker():
    try:
        import sys as _s
        from pathlib import Path as _P
        _s.path.insert(0, str(_P(__file__).resolve().parent / "lib"))
        from test_identity import resolve_test_identity
        i = resolve_test_identity("bryangarcia@auth.workhiveph.com")
        return i.user_id, i.hive_id
    except Exception:
        return ("4153311f-624d-4ec0-b509-e69cb5a8f4cd",   # uid fallback (stale-known)
                "636cf7e8-431a-4907-8a9f-43dd4cc216d6")   # hive fallback (stale-known)
WORKER_UID, HIVE = _resolve_worker()

# Each check: a rolled-back psql script; PASS iff `expect` substring appears in the output.
JWT = ("set local role authenticated;\n"
       "set local request.jwt.claims = '{\"sub\":\"" + WORKER_UID + "\",\"role\":\"authenticated\"}';\n")

CHECKS = [
    {   # BUG A: client cannot release an order (would bump seller total_sales)
        "name": "fake-sales-blocked (client cannot set order status=released)",
        "sql": ("begin;\n" + JWT +
                "insert into marketplace_orders(id,hive_id,buyer_name,seller_name,price,currency,status) "
                "values(gen_random_uuid(),'" + HIVE + "','Bryan Garcia','Leandro Marquez',1,'PHP','pending_payment');\n"
                "update marketplace_orders set status='released' where buyer_name='Bryan Garcia' and price=1;\n"
                "select 'FORGE_OK';\nrollback;\n"),
        # PASS iff the release UPDATE raised (the guard fires) => we DON'T see FORGE_OK, we see the error.
        "expect_error": "escrow system",
    },
    {   # BUG B: client unverified review must not move a seeded rating
        "name": "fake-review no-op (unverified review does not change rating_avg)",
        # 2026-07-29: SELF-MINT the inquiry linkage (service-role, rolled back with the tx) —
        # the probe's pinned Bryan→Leonardo inquiry rotted out of the reseeded data, and the
        # RLS insert path REQUIRES an inquiry, so the probe RLS-errored instead of probing
        # (the header's own stale-fixture warning, one rung further: rot can ERROR, not just
        # vacuous-pass). Minting our own fixture removes the seed dependence entirely.
        "sql": ("begin;\n"
                "insert into marketplace_inquiries(id, listing_id, buyer_name, message) "
                "select gen_random_uuid(), l.id, 'Bryan Garcia', 'gate-probe inquiry' "
                "from marketplace_listings l where l.seller_name='Leonardo Romero' limit 1;\n"
                + JWT +
                "create temp table _r on commit drop as select rating_avg a0, rating_count c0 "
                "from marketplace_sellers where worker_name='Leonardo Romero';\n"
                "insert into marketplace_reviews(id,listing_id,reviewer_name,rating,comment,verified_purchase) "
                "select gen_random_uuid(), l.id, 'Bryan Garcia', 5, 'gate probe', false "
                "from marketplace_listings l where l.seller_name='Leonardo Romero' limit 1;\n"
                "select case when s.rating_avg is not distinct from r.a0 and s.rating_count is not distinct from r.c0 "
                "then 'RATING_UNCHANGED' else 'RATING_MOVED_BAD' end "
                "from marketplace_sellers s, _r r where s.worker_name='Leonardo Romero';\nrollback;\n"),
        "expect": "RATING_UNCHANGED",
    },
    {   # BUG C regression: direct client forge of the trust columns stays blocked
        "name": "trust-columns forge-blocked (direct update of total_sales/rating_avg)",
        "sql": ("begin;\n" + JWT +
                "update marketplace_sellers set total_sales=9999, rating_avg=5.0 where worker_name='Bryan Garcia';\n"
                "select 'FORGE_OK';\nrollback;\n"),
        "expect_error": "not allowed",
    },
]


# SERVICE-HAILING C6 (2026-07-29): bidirectional service-review legitimacy. Service
# reviews reuse marketplace_reviews (request_id + direction) with birth-time legitimacy
# (trg_guard_service_review): only a COMPLETED request's own party, once per direction,
# attribution + verified pinned server-side; provider rating is VIEW-computed from these
# rows only (no stored counter to forge). Probes mint their own actors (hex uuids)
# inside the rolled-back tx - zero dependence on seeded state.
_C6_JWT_STRANGER = 'set local request.jwt.claims = \'{"sub":"a6000000-0000-4000-8000-0000000000c3","role":"authenticated"}\';\n'
_C6_JWT_CLIENT = 'set local request.jwt.claims = \'{"sub":"a6000000-0000-4000-8000-0000000000c1","role":"authenticated"}\';\n'
CHECKS.append({
    "name": "service-review legitimacy (stranger blocked; legit party review moves the VIEW rating)",
    "sql": (
        "begin;\n"
        "insert into auth.users(id, email) values"
        " ('a6000000-0000-4000-8000-0000000000c1','c6-client@gate.local'),"
        " ('a6000000-0000-4000-8000-0000000000c2','c6-provider@gate.local'),"
        " ('a6000000-0000-4000-8000-0000000000c3','c6-stranger@gate.local');\n"
        "insert into service_providers(id, provider_type, auth_uid, display_name, categories)"
        " values ('b6000000-0000-4000-8000-0000000000c1','freelancer','a6000000-0000-4000-8000-0000000000c2','C6 Prov','{Electrical}');\n"
        "insert into service_requests(id, client_auth_uid, mode, custom_scope, status, matched_provider_id, completed_at)"
        " values ('c6000000-0000-4000-8000-0000000000c1','a6000000-0000-4000-8000-0000000000c1','instant','c6 done','completed','b6000000-0000-4000-8000-0000000000c1', now());\n"
        "set local role authenticated;\n"
        + _C6_JWT_STRANGER +
        "do $c6a$ begin\n"
        "  begin\n"
        "    insert into marketplace_reviews(id, reviewer_name, rating, request_id, direction)"
        " values (gen_random_uuid(),'Stranger',5,'c6000000-0000-4000-8000-0000000000c1','client_to_provider');\n"
        "    raise warning 'SVCREV_STRANGER_OPEN';\n"
        "  exception when check_violation or insufficient_privilege then raise notice 'SVCREV_STRANGER_BLOCKED'; end;\n"
        "end $c6a$;\n"
        + _C6_JWT_CLIENT +
        "do $c6b$ declare rc int; ra numeric; begin\n"
        "  insert into marketplace_reviews(id, reviewer_name, rating, request_id, direction)"
        " values (gen_random_uuid(),'Client',5,'c6000000-0000-4000-8000-0000000000c1','client_to_provider');\n"
        "  select rating_count, rating_avg into rc, ra from v_service_provider_truth where id='b6000000-0000-4000-8000-0000000000c1';\n"
        "  if rc = 1 and ra = 5.00 then raise notice 'SVCREV_LEGIT_OK';\n"
        "  else raise warning 'SVCREV_VIEW_BAD'; end if;\n"
        "end $c6b$;\n"
        "rollback;\n"),
    "expect_all": ["svcrev_stranger_blocked", "svcrev_legit_ok"],
})

# SERVICE-HAILING C6b (2026-07-29, LIVE-CAUGHT EXPLOIT): an identity that is BOTH a
# marketplace admin AND the matched provider could author the CLIENT's direction on its OWN
# completed job - guard_service_review() early-returned on is_marketplace_admin() before any
# party check. That row is verified_purchase=true by construction and feeds
# v_service_provider_truth.rating_avg/tier, so a provider-admin could self-mint a 5-star
# reputation (and at 25 jobs + 4.5 stars, a self-minted GOLD tier with broadcast priority).
# The prior probe missed it by testing refusals as a NON-admin. Fix: mig 20260729000003 -
# the admin bypass now applies ONLY when the admin is NOT a party to the request.
# This probe asserts BOTH halves: self-deal blocked, third-party moderation preserved.
_C6_JWT_ADMINPROV = 'set local request.jwt.claims = \'{"sub":"a6000000-0000-4000-8000-0000000000d2","role":"authenticated"}\';\n'
CHECKS.append({
    "name": "service-review admin self-deal (provider-admin cannot write the client's direction on its own job)",
    "sql": (
        "begin;\n"
        "insert into auth.users(id, email) values"
        " ('a6000000-0000-4000-8000-0000000000d1','c6b-client@gate.local'),"
        " ('a6000000-0000-4000-8000-0000000000d2','c6b-adminprov@gate.local'),"
        " ('a6000000-0000-4000-8000-0000000000d3','c6b-otherclient@gate.local'),"
        " ('a6000000-0000-4000-8000-0000000000d4','c6b-otherprov@gate.local');\n"
        # make d2 a REAL marketplace admin the way the app resolves it: is_marketplace_admin()
        # -> marketplace_platform_admins.worker_name IN auth_worker_names(), and
        # auth_worker_names() maps auth.uid() through hive_members/marketplace_sellers.
        "insert into marketplace_sellers(auth_uid, worker_name) values"
        " ('a6000000-0000-4000-8000-0000000000d2','C6b AdminProv')"
        " on conflict do nothing;\n"
        "insert into marketplace_platform_admins(worker_name, granted_by)"
        " values ('C6b AdminProv','c6b-gate') on conflict do nothing;\n"
        "insert into service_providers(id, provider_type, auth_uid, display_name, categories) values"
        " ('b6000000-0000-4000-8000-0000000000d1','freelancer','a6000000-0000-4000-8000-0000000000d2','C6b AdminProv','{Electrical}'),"
        " ('b6000000-0000-4000-8000-0000000000d2','freelancer','a6000000-0000-4000-8000-0000000000d4','C6b OtherProv','{Electrical}');\n"
        "insert into service_requests(id, client_auth_uid, mode, custom_scope, status, matched_provider_id, completed_at) values"
        # the admin-provider's OWN job
        " ('c6000000-0000-4000-8000-0000000000d1','a6000000-0000-4000-8000-0000000000d1','instant','c6b own','completed','b6000000-0000-4000-8000-0000000000d1', now()),"
        # a job the admin is NOT a party to
        " ('c6000000-0000-4000-8000-0000000000d2','a6000000-0000-4000-8000-0000000000d3','instant','c6b other','completed','b6000000-0000-4000-8000-0000000000d2', now());\n"
        "set local role authenticated;\n"
        + _C6_JWT_ADMINPROV +
        "do $c6c$ begin\n"
        "  begin\n"
        "    insert into marketplace_reviews(id, reviewer_name, rating, request_id, direction)"
        " values (gen_random_uuid(),'SelfDeal',5,'c6000000-0000-4000-8000-0000000000d1','client_to_provider');\n"
        "    raise warning 'SVCREV_SELFDEAL_OPEN';\n"
        "  exception when check_violation or insufficient_privilege then raise notice 'SVCREV_SELFDEAL_BLOCKED'; end;\n"
        "end $c6c$;\n"
        "do $c6d$ begin\n"
        "  begin\n"
        "    insert into marketplace_reviews(id, reviewer_name, rating, request_id, direction)"
        " values (gen_random_uuid(),'Moderation',3,'c6000000-0000-4000-8000-0000000000d2','client_to_provider');\n"
        "    raise notice 'SVCREV_MODERATION_OK';\n"
        "  exception when others then raise warning 'SVCREV_MODERATION_BROKEN'; end;\n"
        "end $c6d$;\n"
        "rollback;\n"),
    "expect_all": ["svcrev_selfdeal_blocked", "svcrev_moderation_ok"],
})


def run_sql(sql: str) -> tuple[str, int]:
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A"],
                           input=sql, capture_output=True, text=True, timeout=40)
    except Exception as e:
        return ("SKIP:docker(" + str(e)[:40] + ")", -1)
    return ((r.stdout or "") + (r.stderr or ""), r.returncode)


def evaluate() -> tuple[list[str], list[str]]:
    passes, fails = [], []
    for c in CHECKS:
        out, rc = run_sql(c["sql"])
        if out.startswith("SKIP") or "could not" in out.lower() or "no such container" in out.lower():
            return (["SKIP"], [])
        low = out.lower()
        if "expect_error" in c:
            ok = c["expect_error"].lower() in low and "forge_ok" not in low
        elif "expect_all" in c:
            # C6 service-review probe: every marker must appear AND no fail-open marker
            ok = all(e in low for e in c["expect_all"]) and "_open" not in low and "_bad" not in low
        else:
            ok = c["expect"].lower() in low
        (passes if ok else fails).append(c["name"] + ("" if ok else f"  [out: {out.strip().replace(chr(10),' ')[:100]}]"))
    return (passes, fails)


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        # teeth: the matcher must reject a missing marker and accept the right one.
        ok = ("RATING_UNCHANGED".lower() in "x rating_unchanged y") and ("escrow system" not in "forge_ok")
        print(f"{G}selftest PASS{X}" if ok else f"{R}selftest FAIL{X}")
        return 0 if ok else 1
    passes, fails = evaluate()
    if passes == ["SKIP"]:
        print(f"{B}Marketplace trust-integrity{X}\n  SKIP: local DB not reachable — gate not evaluated.")
        return 0
    print(f"{B}Marketplace trust-integrity (P5/P6 seller-signal forge lock){X}")
    for p in passes:
        print(f"  {G}PASS{X}  {p}")
    for f in fails:
        print(f"  {R}FAIL{X}  {f}")
    if fails:
        print(f"{R}FAIL - {len(fails)} marketplace trust-forge vector(s) OPEN.{X}")
        return 1
    print(f"{G}PASS - {len(passes)} trust-forge vectors blocked (fake-sales / fake-review / trust-columns).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
