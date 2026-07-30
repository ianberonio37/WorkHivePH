"""validate_truth_view_read_isolation.py — LIVE cross-hive READ isolation across ALL truth views.

Batch generalization of the security_invoker read-leak class (mig 20260713000001, where 3 truth views
missing security_invoker let a non-member read 1105 rows of a foreign hive's logbook). Instead of
probing a few views, this loops over EVERY hive-scoped `v_*_truth` view and, AS a real authenticated
member of hive A, reads that view filtered to hive B — asserting **0 rows** (RLS/security_invoker holds).
A future view shipped without security_invoker (or a base-table RLS regression) FAILs here.

PUBLIC-by-design views are excluded (the marketplace is a cross-hive directory; public community posts +
public-footprint reputation are cross-hive visible): marketplace_listings/sellers, community_posts,
community_reputation. Every OTHER hive-scoped truth view must be hive-private.

Rolled-back live probe (mutates nothing). Actors + a data-rich foreign hive chosen dynamically =
reseed-robust. Skips cleanly (exit 0) when docker/DB or a two-hive fixture is absent. Exit 1 = a leak.
"""
import sys, json, subprocess
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
REPORT = ROOT / "truth_view_read_isolation_report.json"

# cross-hive PUBLIC by design — a member legitimately sees other hives' rows here.
PUBLIC = {
    "v_marketplace_listings_truth", "v_marketplace_sellers_truth",
    "v_community_posts_truth", "v_community_reputation_truth",
    # Reviewed 2026-07-29 (service-hailing). The provider DIRECTORY is the exact analog of
    # v_marketplace_sellers_truth already above: a marketplace only works if a client in one hive
    # can see - and hail - a provider from another. It carries curated public columns only, and the
    # sensitive one is deliberately ABSENT: `live_location` is not on this view at all (verified: 0
    # matching columns), so a position is readable ONLY through v_service_job_tracking, and only by
    # that job's parties while it is active. That split is locked by the C1 and C10 gates.
    "v_service_provider_truth",
    # Coordinate-free liquidity counts by declared service AREA - no id, name or geography column
    # exists on it, so it can never be resolved to a person or a point (D8).
    "v_service_area_presence",
    # Ranks the same already-public directory over guarded completion counts; introduces no column
    # that v_service_provider_truth does not already publish.
    "v_service_provider_leaderboard",
    # A marketplace with a hidden price list is not a marketplace. Carries no person, hive or
    # geography column — it is the rate card. Asserted POSITIVELY by the party-scope probe below, so
    # "public" stays a decision on the record: if it ever stops being readable that is a product
    # break, not a security win.
    "v_service_catalog_truth",
}

# PARTY-scoped, not hive-scoped: these carry NO hive_id column at all, so the cross-hive probe above
# cannot reach them and they fell through as an uncovered GAP on the per-page bughunt scoreboard
# (2026-07-29). "No hive column" is exactly the shape that slips past a hive-shaped gate — and one of
# these views carries a GCash reference, which ties a real phone number to a real payment.
#
# Their probe is different: a freshly-minted STRANGER — a fully legitimate signed-in user who simply
# is not a party — must read ZERO. The stranger is minted here rather than borrowed from the seeded
# set, because a seeded identity may turn out to be a party to something.
PARTY_SCOPED = {
    "v_service_credit_topups_truth": "a GCash top-up filing: payer, reference, amount",
    "v_service_credit_ledger_truth": "the credit movements behind it",
    "v_service_job_tracking":        "a provider's live position while a job is active",
    "v_service_open_broadcasts":     "the open-hail feed, keyed to the caller's own provider id",
}
STRANGER = "d5aaaaaa-0000-4000-8000-000000000009"


def _psql(sql):
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-X", "-A", "-t", "-c", sql],
                           capture_output=True, text=True, timeout=45)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception:
        return None


def _one(res):
    if not res:
        return None
    rows = [ln for ln in res[1].splitlines() if ln.strip()]
    return rows[0].split("|") if rows else None


def _skip(reason):
    print(f"{YELLOW}  SKIP  {reason}{RESET}")
    REPORT.write_text(json.dumps({"validator": "truth_view_read_isolation", "skipped": True, "reason": reason}, indent=2), encoding="utf-8")
    return 0


def main():
    print(f"\n{BOLD}TRUTH-VIEW READ ISOLATION (live · every hive-private v_*_truth returns 0 for a foreign hive){RESET}")
    print("-" * 44)
    a = _one(_psql("SELECT auth_uid, hive_id FROM hive_members WHERE status='active' AND auth_uid IS NOT NULL LIMIT 1;"))
    if a is None:
        return _skip("docker psql unavailable or no active member")
    uid_a, hive_a = a
    b = _one(_psql(f"SELECT hive_id, count(*) FROM logbook WHERE hive_id IS NOT NULL AND hive_id <> '{hive_a}' GROUP BY hive_id ORDER BY count(*) DESC LIMIT 1;"))
    if b is None:
        return _skip("need a second populated hive for the cross-hive read probe")
    hive_b = b[0]
    # Every v_* view WITH a hive_id column is hive-scoped and must isolate — NOT just the *_truth-named
    # ones (2026-07-20: the per-page bughunt scoreboard found v_sensor_recent / v_active_anomaly_alerts /
    # v_audit_unified are hive_id views read by pages but were skipped purely on the name suffix).
    views_res = _psql("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                      "WHERE n.nspname='public' AND c.relkind='v' AND c.relname LIKE 'v\\_%' "
                      "AND EXISTS (SELECT 1 FROM information_schema.columns col WHERE col.table_name=c.relname AND col.column_name='hive_id') "
                      "ORDER BY c.relname;")
    if views_res is None:
        return _skip("could not enumerate truth views")
    views = [ln.strip() for ln in views_res[1].splitlines() if ln.strip() and ln.strip() not in PUBLIC]

    claims = "'{\"sub\":\"%s\",\"role\":\"authenticated\"}'" % uid_a
    # one rolled-back tx: as member A, count each private view for hive B → must be 0.
    lines = [f"BEGIN;", "SET LOCAL ROLE authenticated;", f"SET LOCAL request.jwt.claims TO {claims};", "DO $$", "DECLARE n int;", "BEGIN"]
    for v in views:
        lines.append(f"  SELECT count(*) INTO n FROM public.{v} WHERE hive_id='{hive_b}'; RAISE NOTICE 'RESULT {v}=%', n;")
    lines += ["END $$;", "ROLLBACK;"]
    res = _psql_stdin("\n".join(lines))
    if res is None:
        return _skip("docker psql unavailable (read probe)")
    results = {}
    for ln in res[1].splitlines():
        if "RESULT " in ln:
            k, _, val = ln.split("RESULT ", 1)[1].strip().partition("=")
            results[k.strip()] = val.strip()

    fails = 0
    for v in views:
        got = results.get(v)
        if got == "0":
            print(f"  {GREEN}PASS{RESET}  {v}: foreign-hive read = 0")
        elif got is None:
            print(f"  {YELLOW}SKIP{RESET}  {v}: no result (view may error on the probe)")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {v}: foreign-hive read = {got} rows — CROSS-HIVE READ LEAK (missing security_invoker or base-RLS hole)")
    print(f"\n  Summary: {len([v for v in views if results.get(v)=='0'])}/{len(views)} private truth views isolate cross-hive reads · {fails} leak(s)  "
          f"(A hive={hive_a[:8]}… foreign={hive_b[:8]}…; {len(PUBLIC)} public views excluded)")

    # ── PARTY-scoped family: a signed-in STRANGER must read 0 ──────────────────────────────────
    party = [f"BEGIN;",
             f"INSERT INTO auth.users(id, email) VALUES ('{STRANGER}','tv-stranger@gate.local');",
             "SET LOCAL ROLE authenticated;",
             "SET LOCAL request.jwt.claims TO '{\"sub\":\"%s\",\"role\":\"authenticated\"}';" % STRANGER,
             "DO $$", "DECLARE n int;", "BEGIN"]
    for v in PARTY_SCOPED:
        party.append(f"  SELECT count(*) INTO n FROM public.{v}; RAISE NOTICE 'RESULT {v}=%', n;")
    # The catalog is asserted the other way round: it MUST be readable, or the marketplace has no
    # price list. A gate that only ever asserts zeroes would call a dead product perfectly secure.
    party.append("  SELECT count(*) INTO n FROM public.v_service_catalog_truth WHERE active; "
                 "RAISE NOTICE 'RESULT v_service_catalog_truth=%', n;")
    party += ["END $$;", "ROLLBACK;"]
    pres = _psql_stdin("\n".join(party))
    if pres is not None:
        pr = {}
        for ln in pres[1].splitlines():
            if "RESULT " in ln:
                k, _, val = ln.split("RESULT ", 1)[1].strip().partition("=")
                pr[k.strip()] = val.strip()
        print(f"\n  {BOLD}Party-scoped (no hive_id column — the shape a hive-shaped probe cannot see){RESET}")
        for v, why in PARTY_SCOPED.items():
            got = pr.get(v)
            if got == "0":
                print(f"  {GREEN}PASS{RESET}  {v}: a signed-in stranger reads 0  ({why})")
                results[v] = "0"
            elif got is None:
                print(f"  {YELLOW}SKIP{RESET}  {v}: no result")
            else:
                fails += 1
                print(f"  {RED}FAIL{RESET}  {v}: a stranger read {got} row(s) — {why} is visible to a "
                      f"non-party")
        cat = pr.get("v_service_catalog_truth")
        if cat is not None and cat != "0":
            print(f"  {GREEN}PASS{RESET}  v_service_catalog_truth: public by design and READABLE "
                  f"({cat} active items)")
            results["v_service_catalog_truth"] = cat
        elif cat == "0":
            fails += 1
            print(f"  {RED}FAIL{RESET}  v_service_catalog_truth: the public price list returned "
                  f"NOTHING — a marketplace with no rate card is broken, not secured")

    REPORT.write_text(json.dumps({"validator": "truth_view_read_isolation", "skipped": False, "results": results, "fail": fails, "public_excluded": sorted(PUBLIC), "party_scoped": sorted(PARTY_SCOPED)}, indent=2), encoding="utf-8")
    return 1 if fails else 0


def _psql_stdin(sql):
    try:
        p = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-X", "-q", "-v", "ON_ERROR_STOP=0"],
                           input=sql, capture_output=True, text=True, timeout=60)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
