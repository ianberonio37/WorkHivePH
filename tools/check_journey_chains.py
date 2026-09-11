#!/usr/bin/env python3
"""check_journey_chains - which journey archetypes cannot be TRUE in which hive, and why.

Every archetype in prove_full_journeys.mjs declares a CHAIN: the rows that have to exist together for its
story to be true in a given hive. A chain that reads 0 is not a walk failure - it is a statement that the
story has nothing to be about there, and walking it with a browser costs minutes to learn what one query
answers in milliseconds.

WHY (2026-09-09). Walking the tier headlessly, three archetypes failed across three hives for exactly this
reason and the reason only surfaced ~40 minutes in: a fleet hive whose parts had never moved (J23), four
hives with nobody to send a report to (J29), every hive's people with no skills record (J25). Each was a
seed gap the vehicle-seed arc left behind, each fixable in seconds, and each one banked the same failure
across a dozen rows before anyone could see it. Asking every chain FIRST turns a browser-hours discovery
into a one-pass report, which is what "drive the roadmap in real time" means in practice.

Reads the chain SQL out of the prover itself, so the two can never disagree - the same rule the scoreboard
follows about the registry.

    python tools/check_journey_chains.py            # every archetype x every hive
    python tools/check_journey_chains.py --empty    # only the cells that read 0
"""
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")
ONLY_EMPTY = "--empty" in sys.argv


def psql(sql: str, tries: int = 3) -> str:
    for _ in range(tries):
        try:
            r = subprocess.run(
                ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA"],
                input=sql, capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
        except (subprocess.TimeoutExpired, OSError):
            continue
        if r.returncode == 0:
            return (r.stdout or "").strip()
    return "ERR"


def chains() -> dict:
    """Lift each archetype's chain straight out of the prover - never a copy that can drift."""
    src = (ROOT / "tools" / "prove_full_journeys.mjs").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r'^\s*(J\d+):\s*\["([^"]+)",\s*"([^"]+)"\]', src, re.M):
        out[m.group(1)] = (m.group(2), m.group(3))
    return out


def main() -> int:
    if psql("SELECT 1;") == "ERR":
        print("SKIP check-journey-chains - local database not reachable")
        return 0

    hives = [h.split("|") for h in psql("SELECT id::text || '|' || name FROM hives ORDER BY name;").split("\n") if h.strip()]
    ch = chains()
    if not ch:
        print("FAIL check-journey-chains - no chains could be read from prove_full_journeys.mjs")
        return 1

    # ★ONLY THE PAIRS THE REGISTRY ACTUALLY CASTS (2026-09-09). The first version asked every archetype
    # against every hive and reported 40 empty cells - but J8, J17, J18, J21 and J30 are PLANT-ONLY by
    # design (a jeepney line runs no sensor bridge and commissions no energy audit), and the registry casts
    # ZERO rows for them in a fleet hive. Six archetypes' worth of "gaps" were combinations nobody ever
    # intended to exist, and seeding data to satisfy them would have invented a platform that isn't there.
    # A gap only counts where a ROW is waiting on it.
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    rows = reg["trajectories"] if isinstance(reg, dict) else reg
    cast = set()
    for r in rows:
        j = r.get("journey") or {}
        if j.get("archetype") and j.get("vertical"):
            cast.add((j["archetype"], j["vertical"]))

    print(f"  {len(ch)} archetype chain(s) x {len(hives)} hive(s), "
          f"restricted to the {len(cast)} (archetype, vertical) pair(s) the registry actually casts\n")
    empties, errors = [], []
    for arch in sorted(ch, key=lambda a: int(a[1:])):
        what, sql = ch[arch]
        cells = []
        for hid, hname in hives:
            if (arch, hname) not in cast:
                continue
            # $W is the walker. ★AND IT MUST BE THE WALKER THE PROVER WOULD CAST, or this report invents
            # gaps the walk does not have. J28's chain counts the walker's own credits, and prove_full_
            # journeys casts it on that hive's TRADER; asking about the hive's alphabetically-first member
            # instead reported "nothing to be about" for three hives that each held a seller with credits.
            # A pre-flight that models a different cast from the walk is measuring a journey nobody takes.
            if arch == "J28":
                w = psql("SELECT s.worker_name FROM marketplace_sellers s "
                         f"WHERE s.hive_id = '{hid}' "
                         "AND EXISTS (SELECT 1 FROM service_credit_ledger l WHERE l.account_id = s.auth_uid "
                         "AND l.account_type = 'consumer') "
                         "AND s.worker_name NOT IN (SELECT worker_name FROM marketplace_platform_admins) "
                         "ORDER BY s.worker_name LIMIT 1;") or ""
            else:
                w = ""
            if not w:
                w = psql(f"SELECT worker_name FROM hive_members WHERE hive_id = '{hid}' AND status = 'active' "
                         "ORDER BY worker_name LIMIT 1;") or ""
            q = sql.replace("$H", hid).replace("$W", w.replace("'", "''"))
            val = psql(q)
            cells.append((hname, val))
            if val == "ERR" or (val and not val.isdigit()):
                errors.append((arch, hname, val[:60]))
            elif val == "0":
                empties.append((arch, hname, what))
        if not ONLY_EMPTY:
            summary = " ".join(f"{n.split()[0][:6]}={v}" for n, v in cells)
            print(f"  {arch:<5} {summary}")

    print()
    if errors:
        print(f"  {len(errors)} chain(s) could not be ASKED (a broken query is not an empty hive):")
        for a, h, e in errors[:10]:
            print(f"    {a:<5} {h[:26]:<27} {e}")
    if empties:
        print(f"  {len(empties)} (archetype, hive) cell(s) where the story has nothing to be about:")
        for a, h, w in empties[:40]:
            print(f"    {a:<5} {h[:26]:<27} {w[:60]}")
        print("\n  Each is a SEED gap or a mis-specified chain - fix it before walking those rows, or the "
              "walk spends browser-minutes rediscovering what this query already said.")
        return 1
    print("  PASS check-journey-chains - every archetype has something to be about in every hive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
