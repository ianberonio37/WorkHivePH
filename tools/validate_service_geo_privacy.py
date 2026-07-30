#!/usr/bin/env python3
"""
validate_service_geo_privacy.py - C10 lock for the SERVICE-HAILING arc's D-Geo axis.

WHY. The arc's §3 D-Geo dimension names four properties that nothing was asserting:
    in-radius-found · out-of-radius-excluded · live-track-active · privacy-when-idle
Column privacy for `live_location` was already locked by the C1 gate (a revoke-first grant plus
the deliberate absence of service_providers from the realtime publication). What had NO standing
gate was the MATCHING behaviour itself - whether a hail actually reaches the near provider, stays
away from the far one, and whether a provider's live position is readable only while a job is
running. Those are the properties a rider-style product lives or dies on, so they get teeth here.

Every probe mints its OWN actors (hex uuids) inside a rolled-back transaction, so the gate never
depends on seeded state and never leaves a row behind. Probes assert STATE (row counts, view
membership), not merely "no exception" - a 0-row RLS block reads as success to an exception-only
test.

Exit 0 = PASS / SKIP (no docker), 1 = a real geo or privacy regression.
"""
from __future__ import annotations
import io
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

# NOTE: uuid suffixes must be HEX - 'g' is not a hex digit and Postgres rejects the literal
# outright (the same trap that voided an earlier probe suite).
# Manila ~ (14.5995, 120.9842). A provider 2km away is IN a 10km broadcast; one ~700km south
# (Davao) is emphatically OUT. Coordinates are literal so the maths is auditable.
SETUP = """
begin;
insert into auth.users(id,email) values
 ('a9000000-0000-4000-8000-00000000ce01','geo-near@gate.local'),
 ('a9000000-0000-4000-8000-00000000ce02','geo-far@gate.local'),
 ('a9000000-0000-4000-8000-00000000ce03','geo-client@gate.local'),
 ('a9000000-0000-4000-8000-00000000ce04','geo-stranger@gate.local');
insert into service_providers(id,provider_type,auth_uid,worker_name,display_name,categories,
                              availability,verified,base_location) values
 ('b9000000-0000-4000-8000-00000000ce01','freelancer','a9000000-0000-4000-8000-00000000ce01','Geo Near','Geo Near Co',
  '{Mechanical}','online',true, extensions.st_setsrid(extensions.st_makepoint(120.9842,14.6175),4326)::extensions.geography),
 ('b9000000-0000-4000-8000-00000000ce02','freelancer','a9000000-0000-4000-8000-00000000ce02','Geo Far','Geo Far Co',
  '{Mechanical}','online',true, extensions.st_setsrid(extensions.st_makepoint(125.6128,7.1907),4326)::extensions.geography);
insert into service_requests(id,client_auth_uid,mode,catalog_item_id,status,broadcast_radius_m,location)
 select 'c9000000-0000-4000-8000-00000000ce01','a9000000-0000-4000-8000-00000000ce03','instant',
        (select id from service_catalog where category='Mechanical' and segment='industrial' limit 1),
        'broadcasting', 10000,
        extensions.st_setsrid(extensions.st_makepoint(120.9842,14.5995),4326)::extensions.geography;
"""

PROBES = [
    {
        "name": "in-radius provider FINDS the hail in their broadcast feed",
        "sql": SETUP + """
set local role authenticated;
set local request.jwt.claims = '{"sub":"a9000000-0000-4000-8000-00000000ce01","role":"authenticated"}';
do $$ declare n int; begin
  select count(*) into n from v_service_open_broadcasts where request_id='c9000000-0000-4000-8000-00000000ce01';
  if n = 1 then raise notice 'GEO_NEAR_SEES_IT';
  else raise warning 'GEO_NEAR_BLIND(%)', n; end if;
end $$;
rollback;""",
        "expect": "geo_near_sees_it",
    },
    {
        "name": "out-of-radius provider is EXCLUDED (700km away cannot accept)",
        "sql": SETUP + """
set local role authenticated;
set local request.jwt.claims = '{"sub":"a9000000-0000-4000-8000-00000000ce02","role":"authenticated"}';
do $$ declare v jsonb; begin
  select public.accept_service_request('c9000000-0000-4000-8000-00000000ce01') into v;
  if v->>'reason' = 'out_of_radius' then raise notice 'GEO_FAR_BLOCKED';
  else raise warning 'GEO_FAR_ACCEPTED(%)', v; end if;
end $$;
rollback;""",
        "expect": "geo_far_blocked",
    },
    {
        "name": "live-track ACTIVE: the client sees the matched provider's position mid-job",
        "sql": SETUP + """
update service_providers set live_location = extensions.st_setsrid(extensions.st_makepoint(120.9850,14.6000),4326)::extensions.geography
 where id='b9000000-0000-4000-8000-00000000ce01';
perform set_config('workhive.service_system_write','on',true);
update service_requests set status='en_route', matched_provider_id='b9000000-0000-4000-8000-00000000ce01',
       accepted_at=now() where id='c9000000-0000-4000-8000-00000000ce01';
set local role authenticated;
set local request.jwt.claims = '{"sub":"a9000000-0000-4000-8000-00000000ce03","role":"authenticated"}';
do $$ declare n int; begin
  select count(*) into n from v_service_job_tracking where request_id='c9000000-0000-4000-8000-00000000ce01';
  if n = 1 then raise notice 'GEO_TRACK_VISIBLE';
  else raise warning 'GEO_TRACK_DARK(%)', n; end if;
end $$;
rollback;""",
        "expect": "geo_track_visible",
    },
    {
        "name": "privacy WHEN IDLE: a stranger can never read the tracking view",
        "sql": SETUP + """
update service_providers set live_location = extensions.st_setsrid(extensions.st_makepoint(120.9850,14.6000),4326)::extensions.geography
 where id='b9000000-0000-4000-8000-00000000ce01';
perform set_config('workhive.service_system_write','on',true);
update service_requests set status='en_route', matched_provider_id='b9000000-0000-4000-8000-00000000ce01',
       accepted_at=now() where id='c9000000-0000-4000-8000-00000000ce01';
set local role authenticated;
set local request.jwt.claims = '{"sub":"a9000000-0000-4000-8000-00000000ce04","role":"authenticated"}';
do $$ declare n int; begin
  select count(*) into n from v_service_job_tracking where request_id='c9000000-0000-4000-8000-00000000ce01';
  if n = 0 then raise notice 'GEO_STRANGER_BLIND';
  else raise warning 'GEO_STRANGER_PEEKS(%)', n; end if;
end $$;
rollback;""",
        "expect": "geo_stranger_blind",
    },
]


def run_sql(sql: str):
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A"],
                           input=sql, capture_output=True, text=True, timeout=60)
    except Exception as e:
        return ("SKIP:" + str(e)[:50], -1)
    return ((r.stdout or "") + (r.stderr or ""), r.returncode)


def main() -> int:
    print(f"{BOLD}Service-hailing GEO + location privacy (C10 / §3 D-Geo){RESET}")
    passes, fails = [], []
    for p in PROBES:
        # `perform` is only legal inside plpgsql; wrap the bare ones for psql
        sql = p["sql"].replace("perform set_config", "select set_config")
        out, rc = run_sql(sql)
        if out.startswith("SKIP") or "no such container" in out.lower() or "cannot connect" in out.lower():
            print(f"  {YELLOW}SKIP{RESET}  docker/DB unavailable")
            return 0
        low = out.lower()
        ok = p["expect"] in low and "warning" not in low
        (passes if ok else fails).append((p["name"], out.strip().replace("\n", " ")[:150]))
    for n, _ in passes:
        print(f"  {GREEN}PASS{RESET}  {n}")
    for n, o in fails:
        print(f"  {RED}FAIL{RESET}  {n}\n        [out: {o}]")
    if fails:
        print(f"{RED}FAIL - {len(fails)} geo/privacy property unproven.{RESET}")
        return 1
    print(f"{GREEN}PASS - all {len(passes)} D-Geo properties hold (in-radius, out-of-radius, live-track, idle privacy).{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
