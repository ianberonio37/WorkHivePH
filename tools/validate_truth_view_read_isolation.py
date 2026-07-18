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
}


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
    views_res = _psql("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                      "WHERE n.nspname='public' AND c.relkind='v' AND c.relname LIKE 'v\\_%truth' "
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
    REPORT.write_text(json.dumps({"validator": "truth_view_read_isolation", "skipped": False, "results": results, "fail": fails, "public_excluded": sorted(PUBLIC)}, indent=2), encoding="utf-8")
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
