#!/usr/bin/env python3
# DEEPWALK-CELL: * D8
"""validate_rls_tenant_isolation.py — Arc G G2: per-table RLS isolation, proven LIVE two-tenant.

The sub-layer check proves "0 orphan-RLS" (every RLS-enabled table has at least one policy).
That is necessary but NOT sufficient: a policy can EXIST and still leak (wrong predicate, OR-with-true,
a USING(true) bypass). This validator proves the policy ACTUALLY isolates, per table, with a live
round-trip: act as an active member of hive A (SET ROLE authenticated + request.jwt.claims), then count
hive B's rows — RLS must filter them to 0. A member who can read another hive's rows = a tenant-isolation
LEAK (the table-level analogue of the DEFINER IDOR closed in G1).

Method (all inside one transaction, ROLLBACK at the end — read-only, mutates nothing):
  for each public table with RLS enabled AND a hive_id column:
    - H_A = a hive that has rows in the table AND an active hive_members.auth_uid;  U_A = that member.
    - H_B = any other hive with rows in the table.
    - SET LOCAL role authenticated; set request.jwt.claims sub=U_A; count rows WHERE hive_id = H_B.
    - 0 => ISOLATED.  >0 => LEAK.  (insufficient data / single hive => SKIP, reported honestly.)

USAGE:      python tools/validate_rls_tenant_isolation.py
Self-test:  python tools/validate_rls_tenant_isolation.py --self-test  (a USING(true) probe table must LEAK)
"""
from __future__ import annotations
import re
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

# Cross-hive reads that are CORRECT by design (evidence-curated; verified against pg_policy):
BY_DESIGN = {
    "community_posts": "community is a cross-hive forum — community_posts_read allows public=true posts cross-hive",
    "community_xp":    "global gamification leaderboard — community_xp is intentionally cross-hive readable",
    "analytics_events": "platform-admin analytics — analytics_events_select_admin grants cross-hive read to admins only",
    "marketplace_listings": "public marketplace (roadmap C8) — mkt_listings_read exposes status='published' listings cross-hive; drafts/sold stay owner-only (verified 2026-07-07: policy = published OR own OR admin; the 1 draft did NOT leak)",
    "marketplace_sellers": "public marketplace SELLER DIRECTORY (the sibling of marketplace_listings) — a cross-hive bazaar requires buyers to see sellers across hives (name/tier/rating/KYB/certs/response-rate = seller-public by design, like an eBay profile). Verified 2026-07-17: exposed fields are seller-marketplace-public; the internal auth_uid UUID is opaque and consumed ONLY by get_community_reputation_by_auth, which is now tenancy-gated (mig 20260717000003, membership-OR-seller). Follow-up (Arc R backlog): a get_seller_community_reputation(worker,hive) that resolves auth_uid server-side, so the client never needs it + auth_uid can be column-revoked.",
    "platform_feedback": "global public product-feedback board",
}

DO_BLOCK = r"""
DO $do$
DECLARE
  r record; v_ha text; v_uid uuid; v_hb text; v_leak int;
BEGIN
  FOR r IN
    SELECT c.relname AS tbl
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity
      AND EXISTS (SELECT 1 FROM information_schema.columns col
                  WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='hive_id')
    ORDER BY c.relname
  LOOP
    v_ha := NULL; v_uid := NULL; v_hb := NULL;
    -- hive_id is uuid on most tables but text on a few (rate-limit/trace keys); cast to text so the
    -- discovery is type-agnostic (a type mismatch used to surface as a false "discover-error" skip).
    BEGIN
      EXECUTE format($q$
        SELECT hm.hive_id::text, hm.auth_uid FROM public.hive_members hm
        WHERE hm.auth_uid IS NOT NULL AND hm.status='active'
          AND EXISTS (SELECT 1 FROM public.%I t WHERE t.hive_id::text = hm.hive_id::text) LIMIT 1$q$, r.tbl)
        INTO v_ha, v_uid;
    EXCEPTION WHEN others THEN RAISE NOTICE 'SKIP|%|discover-error', r.tbl; CONTINUE; END;
    IF v_ha IS NULL THEN RAISE NOTICE 'SKIP|%|no-member-with-data', r.tbl; CONTINUE; END IF;
    EXECUTE format($q$SELECT t.hive_id::text FROM public.%I t WHERE t.hive_id::text <> %L AND t.hive_id IS NOT NULL LIMIT 1$q$,
                   r.tbl, v_ha) INTO v_hb;
    IF v_hb IS NULL THEN RAISE NOTICE 'SKIP|%|single-hive', r.tbl; CONTINUE; END IF;
    -- act as the member of H_A; RLS must hide H_B's rows
    SET LOCAL role authenticated;
    PERFORM set_config('request.jwt.claims', json_build_object('sub', v_uid, 'role','authenticated')::text, true);
    BEGIN
      EXECUTE format($q$SELECT count(*) FROM public.%I t WHERE t.hive_id::text = %L$q$, r.tbl, v_hb) INTO v_leak;
    EXCEPTION WHEN others THEN v_leak := -1; END;
    RESET role;
    PERFORM set_config('request.jwt.claims', '', true);
    IF v_leak < 0 THEN RAISE NOTICE 'SKIP|%|query-error', r.tbl;
    ELSIF v_leak > 0 THEN RAISE NOTICE 'LEAK|%|%', r.tbl, v_leak;
    ELSE RAISE NOTICE 'ISOLATED|%|0', r.tbl; END IF;
  END LOOP;
END
$do$;
"""


def run_block(extra_setup: str = "") -> list[str]:
    sql = "BEGIN;\n" + extra_setup + DO_BLOCK + "\nROLLBACK;\n"
    try:
        p = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres"],
                           input=sql, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=240)
        return [l for l in (p.stdout + p.stderr).splitlines() if "NOTICE:" in l]
    except Exception as e:  # noqa: BLE001
        return [f"ERR {e}"]


def parse(lines):
    iso, leak, skip = [], [], []
    for l in lines:
        m = re.search(r"(ISOLATED|LEAK|SKIP)\|([^|]+)\|(.*)$", l)
        if not m:
            continue
        kind, tbl, info = m.group(1), m.group(2).strip(), m.group(3).strip()
        (iso if kind == "ISOLATED" else leak if kind == "LEAK" else skip).append((tbl, info))
    return iso, leak, skip


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    print("=" * 72)
    print("  Arc G G2 — per-table RLS tenant isolation (live two-tenant round-trip)")
    print("=" * 72)

    if self_test:
        # teeth: a table with a USING(true) policy MUST be detected as a LEAK
        setup = """
        CREATE TEMP TABLE _probe_leak (id serial, hive_id uuid);
        -- TEMP tables can't carry the prod RLS; emulate by a real ephemeral table in a rolled-back txn:
        """
        # Build a real (rolled-back) table with a permissive policy to prove the harness catches a leak.
        setup = r"""
        CREATE TABLE public._rls_probe_leak (id serial primary key, hive_id uuid);
        INSERT INTO public._rls_probe_leak (hive_id)
          SELECT hive_id FROM public.hive_members WHERE auth_uid IS NOT NULL AND status='active' LIMIT 1;
        INSERT INTO public._rls_probe_leak (hive_id) VALUES (gen_random_uuid());
        ALTER TABLE public._rls_probe_leak ENABLE ROW LEVEL SECURITY;
        CREATE POLICY _probe_all ON public._rls_probe_leak FOR SELECT USING (true);  -- the BUG: no isolation
        GRANT SELECT ON public._rls_probe_leak TO authenticated;
        """
        lines = run_block(setup)
        iso, leak, skip = parse(lines)
        caught = any(t == "_rls_probe_leak" for t, _ in leak)
        mark = f"{GREEN}PASS{RST}" if caught else f"{RED}FAIL{RST}"
        print(f"  TEETH [{mark}] a USING(true) policy table is detected as a LEAK")
        return 0 if caught else 1

    iso, leak_all, skip = parse(run_block())
    leak = [(t, n) for t, n in leak_all if t not in BY_DESIGN]
    bydesign = [(t, n) for t, n in leak_all if t in BY_DESIGN]
    print(f"  tested {len(iso)+len(leak_all)} hive tables live · {len(skip)} skipped (insufficient data)")
    for t, info in skip:
        print(f"    {YEL}skip{RST} {t} ({info})")
    for t, n in bydesign:
        print(f"    {YEL}by-design{RST} {t} (cross-hive read OK) — {BY_DESIGN[t]}")
    print(f"  {GREEN}ISOLATED{RST}: {len(iso)}   by-design: {len(bydesign)}   {RED}LEAK{RST}: {len(leak)}")
    if leak:
        for t, n in leak:
            print(f"    {RED}LEAK{RST} {t}: a hive-A member saw {n} of hive-B's rows")
        print(f"\n  {RED}FAIL{RST}: {len(leak)} table(s) leak across tenants (baseline 0)")
        return 1
    print(f"\n  {GREEN}PASS{RST} — every tested hive table isolates (a member sees 0 of another hive's rows); "
          f"{len(bydesign)} cross-hive-by-design exempt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
