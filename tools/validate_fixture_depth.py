#!/usr/bin/env python3
"""validate_fixture_depth.py — every MOMENT a trajectory names must be one its hive has actually lived.

WHY THIS EXISTS (W3-JN, 2026-09-10). 49 journey rows carry a `moment` — `month-3`, `year-2`, or the
Tier-D `day-1+month-3+year-2` — and a moment is not a setting the walk applies; it is a FACT about the
hive's history that the walk verifies. `prove_full_journeys.mjs` checks it honestly and fails the row
when it is not true:

    this row is set at "year-2", which needs about 730 days of history; this hive holds 90.
    The moment it names is not one this hive has lived, so the walk is about today's data wearing
    another date.

That sentence was recorded SIXTEEN times across NINE archetypes as a fixture gap awaiting a data
decision. It was not a data decision. `tools/seed_5y_synthetic_history.py` read its own asset inventory
with `logbook?select=hive_id,machine&limit=2000` against a 3,847-row table, so whichever hives fell
inside that window got five years of history and the other three got none — and its checkpoint guard
then asked for `max(days)` across hives, so the ONE deep hive certified all six. Both numbers were true;
neither answered the question being asked. Fixed, the same 22 `year-2` rows walked 22/22 on the first
re-run, and nothing about the product had ever been wrong.

WHAT THIS GATE ADDS THAT THE SEEDER'S OWN CHECKPOINT CANNOT. The checkpoint answers "did I run?". This
answers "is the corpus deep enough for what the REGISTRY asks of it?" — which is the question that
actually bites, and it is asked of the database rather than of a file in `.tmp/`. It matters because the
failure is silent and slow: `test-data-seeder/seeders/reset.py` truncates `logbook` without touching
`.tmp/`, so a reset re-shallows every hive while the receipt still says 20,600 rows, and the only symptom
is journey rows failing one at a time, months later, in a sentence that reads like a product limitation.

    python tools/validate_fixture_depth.py
    python tools/validate_fixture_depth.py --selftest
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"

# The same table prove_full_journeys.mjs uses (MOMENTS_NEEDED). Kept in step deliberately: a gate that
# invented its own thresholds would pass a corpus the walk then rejects, which is worse than no gate.
MOMENTS_NEEDED = {"month-3": 90, "year-2": 730, "day-1+month-3+year-2": 730}


def _psql(sql: str) -> str | None:
    """The database's own answer, or None when it cannot be reached.

    None rather than '' on failure, because an unreachable database must never read as "every hive has
    zero days of history" — that would turn a docker hiccup into 49 confident findings. The one rule this
    whole wave keeps re-learning.
    """
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres",
             "-d", "postgres", "-tA", "-c", sql],
            capture_output=True, text=True, timeout=40, encoding="utf-8", errors="replace")
        return out.stdout if out.returncode == 0 else None
    except Exception:
        return None


def hive_spans() -> dict[str, int] | None:
    """{hive name: logbook SPAN in days}. The SPAN (max - min), not the age of the oldest row, because
    that is what a `year-2` walk asks of a hive: two years it has lived, not one ancient row and a gap."""
    raw = _psql("select h.name || '|' || "
                "(extract(epoch from (max(l.created_at) - min(l.created_at))) / 86400)::int "
                "from hives h join logbook l on l.hive_id = h.id group by h.name")
    if raw is None:
        return None
    out: dict[str, int] = {}
    for line in raw.splitlines():
        name, sep, days = line.rpartition("|")
        if sep and days.strip().lstrip("-").isdigit():
            out[name.strip()] = int(days.strip())
    return out


def moment_density() -> dict[tuple[str, str], int] | None:
    """{(hive, moment): rows the corpus holds AROUND that moment}.

    ★A SPAN IS NOT A MOMENT (2026-09-10). Everything above asks whether a hive has LIVED long enough
    for the date a row names - and every hive now spans ~1,824 days, so every cast passes. But a walk
    set at `month-3` renders the hive AS IT WAS THEN, and the three fleet hives hold almost nothing in
    those windows: Ramos Jeepney Line has ONE logbook row around month-3, Tan Delivery Vans has ONE
    around year-2, Dela Cruz has three and four. The plants hold 35-324 in the same windows. So a
    fleet row set at a moment measures an almost-empty page and calls it "the hive at month 3" - the
    date is honest and the SCENE is not.

    Reported, not failed, above zero: how much history a small fleet should carry is a fixture
    decision, and a gate that fails the board on a judgement call teaches people to ignore it. ZERO
    rows in the window IS failed, because then the moment does not exist in the data at all.
    """
    windows = {"month-3": ("3 months 15 days", "3 months"),
               "year-2":  ("2 years 15 days", "2 years"),
               "day-1":   ("5 years", "4 years 11 months")}
    out: dict[tuple[str, str], int] = {}
    for moment, (lo, hi) in windows.items():
        raw = _psql(
            "select h.name || '|' || count(*) from hives h join logbook l on l.hive_id = h.id "
            f"where l.created_at between now() - interval '{lo}' and now() - interval '{hi}' "
            "group by h.name")
        if raw is None:
            return None
        for line in raw.splitlines():
            name, sep, n = line.rpartition("|")
            if sep and n.strip().isdigit():
                out[(name.strip(), moment)] = int(n.strip())
    return out


def demanded() -> dict[str, set[str]]:
    """{vertical (hive name): set of moments the registry casts there}. Read from the rows themselves, so
    a moment added to the grid tomorrow is covered without editing this file."""
    reg = json.loads(io.open(REGISTRY, encoding="utf-8").read())
    rows = reg["trajectories"] if isinstance(reg, dict) else reg
    want: dict[str, set[str]] = {}
    for t in rows:
        j = t.get("journey") or {}
        moment, vertical = j.get("moment"), j.get("vertical")
        if moment in MOMENTS_NEEDED and vertical:
            want.setdefault(vertical, set()).add(moment)
    return want


def shortfalls(spans: dict[str, int], want: dict[str, set[str]]) -> list[tuple[str, str, int, int]]:
    """(hive, moment, needed, held) for every cast the corpus cannot honestly support."""
    out = []
    for hive, moments in sorted(want.items()):
        held = spans.get(hive)
        for m in sorted(moments):
            need = MOMENTS_NEEDED[m]
            if held is None:
                out.append((hive, m, need, -1))       # cast somewhere with no logbook history at all
            elif held < need:
                out.append((hive, m, need, held))
    return out


def run() -> int:
    want = demanded()
    if not want:
        print("fixture-depth: no trajectory names a moment - nothing to require")
        return 0
    spans = hive_spans()
    if spans is None:
        # An unverifiable claim is left alone rather than failed: the same rule the seeder's checkpoint
        # follows. A gate that fails on its own outage teaches people to ignore it.
        print("fixture-depth: the database could not be read, so corpus depth is UNVERIFIED (not failed)")
        return 0
    bad = shortfalls(spans, want)

    # ── density at the moment, not just span to it ────────────────────────────
    THIN = 10                      # below this a moment renders as a near-empty page
    dens = moment_density()
    empty, thin = [], []
    if dens is not None:
        # A Tier-D compound moment expands into its parts, and those parts overlap the standalone
        # casts - so collect the (hive, part) pairs into a SET first, or the same shortfall is
        # reported once per row that happens to name it and the count reads like a bigger problem.
        pairs = {(hive, part)
                 for hive, moments in want.items()
                 for m in moments
                 for part in (m.split("+") if "+" in m else [m])}
        for hive, part in sorted(pairs):
            n = dens.get((hive, part))
            if n is None or n == 0:
                empty.append((hive, part))
            elif n < THIN:
                thin.append((hive, part, n))
    print(f"fixture-depth: {len(want)} vertical(s) carry a moment; "
          f"shallowest hive spans {min(spans.values()) if spans else 0} days, deepest {max(spans.values()) if spans else 0}")
    if thin:
        print(f"  NOTE {len(thin)} (hive, moment) pair(s) hold FEWER THAN {THIN} rows in the window - the date is")
        print( "       honest but the scene is nearly empty, so the walk measures a blank page wearing that date:")
        for hive, m, n in thin:
            print(f"         {hive}: \"{m}\" holds {n} row(s)")
        print( "       How much history a small fleet should carry is a fixture decision, so this is reported,")
        print( "       not failed. Zero rows in the window IS failed - see below.")
    if empty:
        print(f"FAIL fixture-depth: {len(empty)} (hive, moment) pair(s) hold NO rows in the window at all:")
        for hive, m in empty:
            print(f"  {hive}: \"{m}\" - the moment does not exist in this hive's data, so no walk can render it")
        return 1
    if not bad:
        for hive in sorted(want):
            print(f"  ok  {hive}: {spans.get(hive)} days covers {', '.join(sorted(want[hive]))}")
        return 0
    print(f"FAIL fixture-depth: {len(bad)} (hive, moment) pair(s) name a moment the hive has not lived:")
    for hive, m, need, held in bad:
        print(f"  {hive}: \"{m}\" needs ~{need} days, holds {'no logbook history at all' if held < 0 else str(held)}")
    print("  A moment is verified against the hive's history, never applied to it - so these rows would\n"
          "  walk today's data wearing another date, and prove_full_journeys.mjs correctly refuses them.\n"
          "  Re-seed:  SUPABASE_SERVICE_ROLE_KEY=<local> python tools/seed_5y_synthetic_history.py --commit\n"
          "  (a reset truncates `logbook` and not `.tmp/`, so the checkpoint can outlive the rows it certifies)")
    return 1


def selftest() -> int:
    fails = 0
    spans = {"Deep Hive": 1800, "Shallow Hive": 52}
    want = {"Deep Hive": {"year-2"}, "Shallow Hive": {"year-2"}, "Ghost Hive": {"month-3"}}
    got = shortfalls(spans, want)
    names = sorted(h for h, *_ in got)
    if names != ["Ghost Hive", "Shallow Hive"]:
        print(f"  FAIL a shallow hive and a hive with no history are the two shortfalls (got {names})")
        fails += 1
    else:
        print("  ok   a deep hive passes; a shallow one and one with no history are both caught")

    # ★THE BUG THIS GATE EXISTS FOR: one deep hive must not vouch for the rest. If shortfalls() were
    # written against max(spans) the Shallow Hive above would pass, which is exactly how 49 rows stayed
    # blocked while the seeder's own checkpoint printed "verified".
    if not any(h == "Shallow Hive" for h, *_ in shortfalls({"A": 1800, "Shallow Hive": 52},
                                                           {"Shallow Hive": {"year-2"}})):
        print("  FAIL a deep sibling is vouching for a shallow hive - the exact defect this gate was written for")
        fails += 1
    else:
        print("  ok   a deep sibling does not vouch for a shallow hive")

    # month-3 is satisfiable at a depth year-2 is not: the thresholds must not be collapsed into one
    if shortfalls({"H": 120}, {"H": {"month-3"}}) or not shortfalls({"H": 120}, {"H": {"year-2"}}):
        print("  FAIL the per-moment thresholds are not being applied separately")
        fails += 1
    else:
        print("  ok   month-3 and year-2 are judged against their own thresholds")

    if _psql("select 1 from a_table_that_does_not_exist") is not None:
        print("  FAIL a failed query is not reported as unreadable")
        fails += 1
    else:
        print("  ok   a failed query reads as unreadable (None), never as zero days")

    print("selftest:", "PASS" if not fails else f"{fails} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
