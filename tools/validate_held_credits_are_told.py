#!/usr/bin/env python3
"""held-credits-are-told - T94: a wallet must not offer credits that are already spoken for (2026-08-27).

Listing on the marketplace HOLDS credits: guard_listing_requires_reservation writes a
credit_reservations row, sweep_listing_holding_fee eats into it monthly, and
release_reservation_on_delist gives it back. The seller page even says so at listing time - "holds
P50 in credits". Held credits are not spendable.

★THE PLATFORM ALREADY COMPUTES THE DISTINCTION. seller_credit_balance(worker_name) returns THREE
numbers - available, reserved, total - where available = ledger balance MINUS everything held. The
wallet card called provider_credit_balance() instead, which returns the ledger sum alone, and
labelled it the balance. So a seller with live listings was shown a number larger than what they
could actually spend, on the same page that had just told them listing would hold some of it.

That is not a missing feature, it is the glass reading the wrong one of three numbers that were
sitting there - the "built but never called" shape, with money in it.

TWO ASSERTIONS:
  1. THE DB STILL DISTINGUISHES: with a held reservation in place, seller_credit_balance's
     available is strictly less than its total by exactly the held amount. Driven live inside a
     transaction that is ROLLED BACK, because credit_reservations is empty on this stack and an
     assertion about holds needs a hold to exist.
  2. THE GLASS SAYS IT: the seller wallet surfaces what is RESERVED, not only a single balance.

Self-test: `--selftest` (the copy assertions).
"""
import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
PAGE = ROOT / "marketplace-seller.html"
# id is a uuid, so the "marker" is a fixed, recognisable uuid rather than a label; listing_id is
# nullable and FK-constrained, so the probe row carries none rather than inventing a listing.
MARKER = "00000000-0000-4000-8000-0000t94h01d0".replace("t", "0").replace("h", "0").replace("d", "0")

# The wallet must name what is held. Matched by meaning: "reserved", "held", "on hold".
NAMES_HELD = re.compile(r"reserved|\bheld\b|on hold|holding", re.I)


def psql(sql: str):
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                        "-t", "-A", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=90)
    return (r.stdout or "").strip(), (r.stderr or "").strip(), r.returncode


def check_glass(src: str) -> list:
    """The wallet card must surface the held amount, not just one balance."""
    m = re.search(r"async function svcWalletHtml[\s\S]{0,4000}", src)
    if not m:
        return ["the seller wallet card (svcWalletHtml) is gone - this gate is aimed at nothing"]
    card = m.group(0)
    problems = []
    if "seller_credit_balance" not in card and "credit_reservations" not in card:
        problems.append("the wallet never asks what is HELD - it reads a single balance, so credits "
                        "already committed to live listings are offered as spendable")
    elif not NAMES_HELD.search(card):
        problems.append("the wallet reads the held amount but never NAMES it on the glass, so the "
                        "number is fetched and then hidden from the person it concerns")
    return problems


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    bare = ("async function svcWalletHtml(provId) {\n"
            "  const { data } = await db.rpc('provider_credit_balance', { p_provider_id: provId });\n"
            "  return `<div>Balance ${data}</div>`;\n}")
    chk("a single-balance wallet fails", len(check_glass(bare)), 1)

    fetched = bare.replace("provider_credit_balance', { p_provider_id: provId }",
                           "seller_credit_balance', { p_seller: WORKER_NAME }")
    chk("fetching the split but not showing it still fails", len(check_glass(fetched)), 1)

    shown = fetched.replace("<div>Balance ${data}</div>", "<div>Available ${a} · reserved ${r}</div>")
    chk("fetching AND naming what is reserved passes", len(check_glass(shown)), 0)
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    print("T94 held credits are told")
    glass = check_glass(io.open(PAGE, encoding="utf-8", errors="replace").read())
    print(f"  wallet names what is held: {'yes' if not glass else 'NO'}")

    # A seller who OWNS a listing: credit_reservations enforces num_nonnulls(listing_id,
    # request_id) = 1, so the probe row has to point at something real. Referencing an existing
    # listing inside a rolled-back transaction changes nothing about it.
    row, err, _ = psql("""
SELECT l.id||'|'||l.seller_name FROM marketplace_listings l
JOIN marketplace_sellers ms ON ms.worker_name = l.seller_name
WHERE ms.auth_uid IS NOT NULL LIMIT 1;""")
    seller = row.split("|", 1)[1] if row and "|" in row else None
    listing = row.split("|", 1)[0] if row and "|" in row else None
    if not seller:
        print(f"  SKIP db half — no seller to probe ({err[:70]})")
        for g in glass:
            print(f"    {g}")
        return 1 if glass else 0

    # credit_reservations is empty on this stack, so the hold is CREATED here and rolled back -
    # an assertion about held credits needs a held credit to exist.
    out, notices, _ = psql(f"""
begin;
insert into credit_reservations (id, seller_name, listing_id, amount, state)
values ('{MARKER}'::uuid, '{seller}', '{listing}'::uuid, 50, 'held');
select 'SPLIT|'||available||'|'||reserved||'|'||total from public.seller_credit_balance('{seller}');
rollback;""")
    split = re.search(r"SPLIT\|([-\d.]+)\|([-\d.]+)\|([-\d.]+)", out or "")
    resid, _, _ = psql(f"SELECT count(*) FROM credit_reservations WHERE id='{MARKER}'::uuid;")

    problems = list(glass)
    if not split:
        print(f"  db half could not run: {(notices or out)[:120]}")
        problems.append("seller_credit_balance did not return an available/reserved/total split")
    else:
        avail, res, total = (float(x) for x in split.groups())
        print(f"  with a 50-credit hold: available={avail} reserved={res} total={total}")
        if not (res > 0 and abs((total - res) - avail) < 0.001):
            problems.append(f"available ({avail}) is not total ({total}) minus reserved ({res}) - "
                            f"the DB's own split no longer holds")
    print(f"  probe reservation left behind: {resid}")
    if (resid or "").strip() != "0":
        problems.append("the probe reservation survived the rollback")

    if not problems:
        print("\n  PASS - the DB splits held from spendable, and the wallet says so.")
        return 0
    print("\n  FAIL")
    for p in problems:
        print(f"    {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
