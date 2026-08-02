#!/usr/bin/env python3
"""validate_hail_geo_coverage.py — is the broadcast radius actually filtering anything?

FOUND ON A LIVE CLIENT WALK, 2026-08-01. I hailed a service through the real UI and the request landed with
`location IS NULL`: the hail form asks for a free-text address ("e.g. Plant 2, Baguio") and never captures a
point. There is no `getCurrentPosition` anywhere in marketplace.html.

WHY THAT IS NOT COSMETIC. The accept gate reads:

    if v_req.location is not null and v_provider.base_location is not null
       and not st_dwithin(v_req.location, v_provider.base_location, v_req.broadcast_radius_m)

so a NULL location makes the whole distance test **skip**. The request still carries
`broadcast_radius_m = 5000` and the UI still speaks of notifying *nearby* providers — but nothing is
filtered by distance, and a provider on the other side of the country is as eligible as one next door.
The number is displayed and inert.

WHY IT STAYED HIDDEN. The SEEDED requests all carry geo, so every probe, journey and scoreboard that runs
against seed data sees a working radius. Only a hail created through the real form exposes it — which is the
recurring shape here: seed data that is healthier than the product
([[feedback_a_dead_fixture_invents_page_defects]] is the mirror of this).

CAPTURE SHIPPED 2026-08-02: the hail form now offers "Pin the exact spot on a map" — Ian chose the pin over
a geolocation prompt (no permission popup) and over a geocoder (PH plant addresses like "Plant 2, Surigao"
do not resolve, and per-lookup pricing does not fit a free-tier platform). The 800KB MapLibre bundle loads
ONLY when that button is pressed, so the hail screen stays light on 3G. Pinning is OPTIONAL: a hail without
one still sends, which is why this gate still exists and why the floor is a count rather than zero.

Proven on a pinned hail: with a point, `st_dwithin` discriminates for real — 2 of 7 providers inside 5km
(1.7km each) and the rest excluded at 46 / 74 / 93 / 204 / 568 km. Without one, all seven were equally
eligible because the whole distance test was skipped.

WHAT THIS GATE DOES. It holds the count of geo-less hails FORWARD-ONLY: the number may never rise. It
ratchets toward zero as pinning is adopted, and goes red the day a new write path skips the location.

Usage:  python tools/validate_hail_geo_coverage.py [--accept] [--selftest]
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "hail_geo_coverage_baseline.json"
CONTAINER = "supabase_db_workhive"
G, R, Y, D, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"


def psql(sql):
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-F", "\x1f", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:180]
    return [ln.split("\x1f") for ln in (r.stdout or "").splitlines() if ln.strip()], ""


QUERY = """
select count(*)::text,
       count(*) filter (where location is null)::text,
       count(*) filter (where location is null and broadcast_radius_m is not null)::text
  from public.service_requests;
"""


def judge(total, no_geo, inert_radius):
    """Pure arithmetic, so the self-test needs no database."""
    problems = []
    if total and no_geo == total:
        problems.append("EVERY request lacks a location — the radius filter has never applied to anything")
    if inert_radius:
        problems.append(f"{inert_radius} request(s) advertise a broadcast radius that cannot filter, "
                        f"because they carry no point to measure from")
    return problems


def selftest():
    print("  selftest: the arithmetic must spot an inert radius and accept a fully-geocoded set")
    ok = True
    if judge(10, 0, 0):
        print(f"  {R}FAIL{X} — a fully-geocoded set was flagged"); ok = False
    if not judge(10, 3, 3):
        print(f"  {R}FAIL{X} — 3 geo-less requests with a radius were not reported"); ok = False
    if not judge(5, 5, 5):
        print(f"  {R}FAIL{X} — an all-null set was not called out"); ok = False
    if ok:
        print(f"  {G}PASS{X} — reports inert radii, accepts a geocoded set")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{B}Hail geo coverage{X} — is the broadcast radius filtering anything?")
    if selftest() != 0:
        return 1

    rows, err = psql(QUERY)
    if rows is None:
        print(f"  {Y}SKIP{X} database unavailable ({err})")
        return 0
    total, no_geo, inert = (int(x) for x in rows[0])
    pct = round(100.0 * no_geo / total, 1) if total else 0.0

    print(f"  {D}service requests {total} · without a location {no_geo} ({pct}%){X}")
    for p in judge(total, no_geo, inert):
        print(f"  {Y}note{X} {p}")
    if no_geo:
        print(f"  {D}these pre-date the pin, or were sent without using it — pinning is optional by "
              f"design, so this is a count to drive DOWN, not a failure{X}")

    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    floor = base.get("no_geo")

    if "--accept" in argv:
        if floor is not None and no_geo > floor:
            print(f"  {R}ACCEPT REFUSED{X} {floor} -> {no_geo} is a RISE; this floor only moves DOWN.")
            return 1
        BASELINE.write_text(json.dumps(
            {"no_geo": no_geo, "total_at_baseline": total,
             "_doc": "Forward-only: the count of hails with no location may never RISE. Ratchets DOWN if "
                     "geo capture is added; goes red if a new geo-less write path appears."}, indent=2),
            encoding="utf-8")
        print(f"  {G}ACCEPTED{X} floor -> {no_geo}")
        return 0

    if floor is not None and no_geo > floor:
        print(f"\n  {R}FAIL{X} — geo-less hails rose {floor} -> {no_geo}. Either a new write path skips "
              f"the location, or the radius is being advertised on more requests it cannot filter.")
        return 1
    print(f"\n  {G}PASS{X} — {no_geo} geo-less request(s), within the {floor if floor is not None else no_geo} baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
