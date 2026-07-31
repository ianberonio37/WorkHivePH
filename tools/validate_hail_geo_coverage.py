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

WHAT THIS GATE DOES, AND DELIBERATELY DOES NOT DO. It does not fail the build for the missing feature —
capturing a client's coordinates needs either a browser geolocation PROMPT or an external geocoder, and both
are product/privacy decisions that belong to Ian, not to a validator. It makes the gap MEASURED and
FORWARD-ONLY: the share of hails with no geo may not grow. If the capture is ever added, this ratchets down
toward zero; if someone adds another geo-less write path, it goes red the same day.

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
        print(f"  {D}the UI hail form captures a free-text address and no point; capturing one needs a "
              f"browser permission prompt or a geocoder — a product decision, not a validator's{X}")

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
