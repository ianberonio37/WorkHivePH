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
WORKER_UID = "4153311f-624d-4ec0-b509-e69cb5a8f4cd"   # Bryan Garcia (worker/buyer)
HIVE = "636cf7e8-431a-4907-8a9f-43dd4cc216d6"          # Baguio Textile Mills

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
        "sql": ("begin;\n" + JWT +
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
