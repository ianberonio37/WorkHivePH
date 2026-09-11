#!/usr/bin/env python3
"""backfill_marketplace_participation - let every hive take part in the marketplace it is cast in.

WHY THIS EXISTS (2026-09-09, found walking J28). The marketplace is a platform-wide feature and the
trajectory registry casts all six hives in it - 69 rows across J5 (parts procurement), J6 (hire a
specialist), J27 (a deal goes wrong) and J28 (top-up -> credits -> spend -> receipt), twelve of them in a
FLEET hive. But `marketplace_sellers` held rows for the three PLANT hives only:

    Manila Electronics  6      Dela Cruz Delivery Fleet  0
    Lucena Pharma       4      Ramos Jeepney Line        0
    Baguio Textile      3      Tan Delivery Vans         0

So a jeepney line could not list a part, could not be hailed for a job, and - because
`claim_starter_grant()` is gated on holding a seller profile - could not hold a single credit. Those
twelve journeys had nobody on the platform who could take them. That is a seed gap, not a design
decision: a fleet operator selling a spare part is exactly the trade this marketplace exists for, and
the roadmap says so by casting them.

WHAT IT WRITES, and why each field is what it is:
  - ONE seller profile per seller-less hive, on that hive's own supervisor (the person who would sign the
    business up), shaped like the real rows already there: tier 'bronze', kyb_verified false, no invented
    ratings or sales. A NEW seller has no history, and inventing one would put a reputation on a page
    that nobody earned.
  - then that person CLAIMS THEIR STARTER GRANT through the platform's own `claim_starter_grant()` RPC -
    not an INSERT of my own. The function issues against the supply cap, records the grant, and writes
    the ledger entry itself, so the credits exist the way every real one does. It refuses politely if
    already claimed, so re-runs are safe.

    python tools/backfill_marketplace_participation.py            # write
    python tools/backfill_marketplace_participation.py --check    # report only
"""
import io
import os
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")
CHECK = "--check" in sys.argv


def psql(sql: str) -> str:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA"],
            input=sql, capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
    except (subprocess.TimeoutExpired, OSError):
        return "ERR"
    return (r.stdout or "").strip() if r.returncode == 0 else "ERR"


def q(s: str) -> str:
    return (s or "").replace("'", "''")


def main() -> int:
    if psql("SELECT 1;") == "ERR":
        print("SKIP backfill-marketplace-participation - local database not reachable")
        return 0

    print("  hive                          sellers  credit_entries")
    for row in psql(
        "SELECT h.name || '|' || count(DISTINCT s.id) || '|' || count(DISTINCT l.id) "
        "FROM hives h LEFT JOIN marketplace_sellers s ON s.hive_id = h.id "
        "LEFT JOIN service_credit_ledger l ON l.account_id = s.auth_uid AND l.account_type = 'consumer' "
        "GROUP BY h.name ORDER BY h.name;"
    ).split("\n"):
        if row.strip():
            n, sc, lc = row.split("|")
            print(f"  {n[:28]:<30}{sc:>5}{lc:>15}")

    # a hive with NO seller cannot take part in any marketplace journey it is cast in
    need = [r.split("|") for r in psql(
        "SELECT h.id::text || '|' || h.name FROM hives h "
        "WHERE NOT EXISTS (SELECT 1 FROM marketplace_sellers s WHERE s.hive_id = h.id) ORDER BY h.name;"
    ).split("\n") if r.strip()]

    # ...and a hive whose seller has never claimed their credits still cannot walk the CREDIT story (J28),
    # whose chain counts that person's own consumer ledger entries. Baguio Textile Mills had three sellers
    # and zero credits: able to list, unable to pay for the listing. Same platform path, same RPC.
    uncredited = [r.split("|") for r in psql(
        "SELECT h.id::text || '|' || h.name || '|' || s.worker_name || '|' || s.auth_uid::text "
        "FROM hives h JOIN marketplace_sellers s ON s.hive_id = h.id "
        "WHERE s.auth_uid IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM service_credit_ledger l WHERE l.account_id = s.auth_uid "
        "AND l.account_type = 'consumer') "
        # ★AND THE HOLDER MUST BE SOMEBODY A JOURNEY MAY BE CAST ON. Lucena had a credit-holder all along -
        # Pablo Aguilar, who is in marketplace_platform_admins - so this hive looked covered while every
        # castable person in it held nothing. An admin's credits are not evidence about a buyer, so they do
        # not satisfy the hive: the check counts only NON-ADMIN holders, the same rule the prover casts by.
        "AND NOT EXISTS (SELECT 1 FROM service_credit_ledger l2 JOIN marketplace_sellers s2 "
        "ON s2.auth_uid = l2.account_id WHERE s2.hive_id = h.id AND l2.account_type = 'consumer' "
        "AND s2.worker_name NOT IN (SELECT worker_name FROM marketplace_platform_admins)) "
        "AND s.worker_name NOT IN (SELECT worker_name FROM marketplace_platform_admins) "
        "ORDER BY h.name, s.worker_name;"
    ).split("\n") if r.strip()]
    seen_hive, to_credit = set(), []
    for hid, hname, worker, uid in uncredited:
        if hid in seen_hive:
            continue
        seen_hive.add(hid)
        to_credit.append((hid, hname, worker, uid))

    if not need and not to_credit:
        print("\nPASS backfill-marketplace-participation - every hive has somebody who can trade, and "
              "somebody who holds credits to trade WITH")
        return 0

    if to_credit:
        print(f"\n  {len(to_credit)} hive(s) can list but hold no credits: "
              f"{', '.join(n for _, n, _, _ in to_credit)}")
        if not CHECK:
            for _hid, hname, worker, uid in to_credit:
                res = psql("SELECT set_config('request.jwt.claims', "
                           f"'{{\"sub\":\"{uid}\",\"role\":\"authenticated\"}}', true), "
                           "public.claim_starter_grant();")
                ok = "true" in (res or "").lower()
                print(f"    + {hname}: {worker} "
                      f"{'claimed their starter credits' if ok else 'could not claim (' + (res or 'no answer')[-40:] + ')'}")

    if not need:
        return 0 if not CHECK else 1

    print(f"\n  {len(need)} hive(s) cast in marketplace journeys with nobody who can trade: "
          f"{', '.join(n for _, n in need)}")
    if CHECK:
        return 1

    made, granted = 0, 0
    for hid, name in need:
        # the hive's own supervisor: the person who would sign the business up
        who = psql(f"SELECT m.worker_name || '|' || m.auth_uid::text FROM hive_members m "
                   f"WHERE m.hive_id = '{hid}' AND m.role = 'supervisor' AND m.status = 'active' "
                   "AND m.auth_uid IS NOT NULL ORDER BY m.worker_name LIMIT 1;")
        if not who or "|" not in who:
            print(f"    ! {name}: no active supervisor with a login - cannot sign anybody up")
            continue
        worker, uid = who.split("|", 1)
        out = psql(
            "INSERT INTO marketplace_sellers (worker_name, auth_uid, hive_id, tier, kyb_verified) "
            f"VALUES ('{q(worker)}', '{uid}', '{hid}', 'bronze', false) RETURNING id;")
        if out == "ERR" or not out:
            print(f"    ! {name}: the seller profile could not be written")
            continue
        made += 1
        # ...and let them claim their credits the way the product does it, AS them
        res = psql("SELECT set_config('request.jwt.claims', "
                   f"'{{\"sub\":\"{uid}\",\"role\":\"authenticated\"}}', true), "
                   "public.claim_starter_grant();")
        ok = "true" in (res or "").lower()
        if ok:
            granted += 1
        print(f"    + {name}: {worker} can now trade"
              f"{' and claimed their starter credits' if ok else ' (grant not claimed: ' + (res or 'no answer')[-40:] + ')'}")

    print(f"\nOK backfill-marketplace-participation - {made} hive(s) gained a trader, {granted} claimed "
          f"their starter grant through the platform's own function. The twelve marketplace journeys cast "
          f"in a fleet hive now have somebody on this platform who could take them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
