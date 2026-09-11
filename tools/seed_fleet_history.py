#!/usr/bin/env python3
"""seed_fleet_history.py — give the three fleet hives a maintenance history they can be walked through.

W3-JN cast its journeys in the platform's own six hives and found that three of them cannot LIVE most of the
stories: Dela Cruz Delivery Fleet, Ramos Jeepney Line and Tan Delivery Vans hold vehicles and **zero logbook
entries, zero PM records and zero alerts**. They were seeded as a vehicle registry, not as an operating
fleet, so "breakdown to close-out", "the PM month" and "audit season" have nothing to be true about there.

Missing data is a seeding job, never a blocker. This writes a small, believable history per fleet - a
handful of jobs against the units they already own, a PM schedule, and the parts those jobs consumed - so a
walk can find a real thread rather than an empty hive.

★TWO THINGS THIS FILE CLAIMED AND DID NOT DO, both found by walking what it produced (2026-09-08):

  1. "the PM records those jobs close" - it never wrote a single one. Its only pm_assets statement was a
     DELETE on revert, filtered on a `notes` column that table does not have, so the delete could only ever
     fail and it failed silently: every revert printed "None PM record(s)" and nobody had a reason to look.

  2. "a handful of jobs against the units they already own" - true unless a fleet owns NONE, and Tan
     Delivery Vans owns none. The `["Unit 1", "Unit 2"]` fallback then broke the file's own rule from the
     other end, writing eight jobs about two vans the product does not have. A delivery-van hive with no
     vans is not a fleet; it now gets vans, cloned from the shape the other two fleets already carry.

★IT CLONES THE PLATFORM'S OWN SHAPE. Every row is modelled on an existing plant-hive row (the same columns,
the same vocabulary, the categories the product already uses), because a seeder that invents its own shape
teaches the walk to expect something the product never writes.

★EVERY ROW IS MARKED AND REVERSIBLE. Each carries the marker below in a free-text column, so --revert
removes exactly what this wrote and nothing else, and re-running never doubles up.

  python tools/seed_fleet_history.py --check     # what each fleet holds today
  python tools/seed_fleet_history.py --apply     # write it
  python tools/seed_fleet_history.py --revert    # remove exactly what this wrote
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

MARKER = "wh-fleet-history-seed"
FLEETS = ["Dela Cruz Delivery Fleet", "Ramos Jeepney Line", "Tan Delivery Vans"]

# Vehicles for a fleet that owns none, modelled on the rows the other two fleets already carry: a plate as
# the tag, "<year> <make> <model>" as the name, equipment / medium / approved, and the same vehicle_meta
# keys the product writes. Only ever used when a fleet has zero assets.
# ★A FLEET OF TWO IS WHY ITS MOMENTS RENDER BLANK (2026-09-10). `seed_5y_synthetic_history.py` writes
# 40 events per ASSET per year, and it did so evenly: rows-per-asset is 200-257 in every hive, plants
# and fleets alike. The fleets are thin because they own 2-3 vehicles against the plants' 30-36 - so a
# Tier-C row cast at `month-3` in Ramos Jeepney Line renders a page holding ONE logbook entry, and
# reports it as "the hive at month 3". The date is honest; the scene is not.
# The fix is vehicles, not more history per vehicle: a jeepney line running two units is not a line.
# FLEET_MIN_UNITS is deliberately modest - enough that a moment window has something in it, not so many
# that a small Philippine operator stops looking like one.
FLEET_MIN_UNITS = 8

VANS = {
    "Tan Delivery Vans": [
        ("TDV 1101", "2021 Toyota HiAce Commuter", "Toyota", "HiAce Commuter", "2021", 142300),
        ("TDV 1102", "2019 Nissan NV350 Urvan", "Nissan", "NV350 Urvan", "2019", 208750),
        ("TDV 1103", "2022 Toyota HiAce Cargo", "Toyota", "HiAce Cargo", "2022", 88400),
        ("TDV 1104", "2018 Hyundai H-100", "Hyundai", "H-100", "2018", 231600),
        ("TDV 1105", "2020 Nissan NV350 Urvan", "Nissan", "NV350 Urvan", "2020", 164200),
        ("TDV 1106", "2017 Mitsubishi L300 FB", "Mitsubishi", "L300 FB", "2017", 279050),
        ("TDV 1107", "2023 Maxus Deliver 9", "Maxus", "Deliver 9", "2023", 41800),
        ("TDV 1108", "2019 Foton Gratour", "Foton", "Gratour", "2019", 197400),
    ],
    "Ramos Jeepney Line": [
        ("RJL 2201", "2016 Sarao Passenger Jeepney", "Sarao", "Passenger Jeepney", "2016", 312400),
        ("RJL 2202", "2015 Morales Passenger Jeepney", "Morales", "Passenger Jeepney", "2015", 358900),
        ("RJL 2203", "2019 Hino Modern Jeepney", "Hino", "Modern Jeepney", "2019", 186300),
        ("RJL 2204", "2018 Isuzu Modern Jeepney", "Isuzu", "Modern Jeepney", "2018", 224700),
        ("RJL 2205", "2014 Celestial Passenger Jeepney", "Celestial", "Passenger Jeepney", "2014", 401250),
        ("RJL 2206", "2021 Hino Modern Jeepney", "Hino", "Modern Jeepney", "2021", 97600),
        ("RJL 2207", "2017 Sarao Passenger Jeepney", "Sarao", "Passenger Jeepney", "2017", 288100),
        ("RJL 2208", "2020 Isuzu Modern Jeepney", "Isuzu", "Modern Jeepney", "2020", 143900),
    ],
    "_default": [
        ("FLT 9001", "2020 Isuzu Traviz", "Isuzu", "Traviz", "2020", 96500),
        ("FLT 9002", "2018 Mitsubishi L300", "Mitsubishi", "L300", "2018", 173900),
        ("FLT 9003", "2021 Isuzu Traviz", "Isuzu", "Traviz", "2021", 78200),
        ("FLT 9004", "2019 Hyundai H-100", "Hyundai", "H-100", "2019", 189400),
        ("FLT 9005", "2022 Isuzu NLR", "Isuzu", "NLR", "2022", 52700),
        ("FLT 9006", "2017 Mitsubishi L300 FB", "Mitsubishi", "L300 FB", "2017", 264800),
        ("FLT 9007", "2020 Foton Tornado", "Foton", "Tornado", "2020", 131500),
        ("FLT 9008", "2023 Isuzu Traviz", "Isuzu", "Traviz", "2023", 29300),
    ],
}

# the jobs a Philippine delivery/jeepney fleet actually records, in the product's own categories
# ★A THIRD THING THIS FILE COMPUTED AND THREW AWAY (2026-09-08). Every tuple below has carried a type and a
# cause since the file was written, and the INSERT listed neither column - so all 24 seeded rows landed with
# a NULL maintenance_type and a NULL root_cause. Measured: they are the ONLY 24 rows on the whole platform
# with a null maintenance_type. Nothing complained, because nothing reads a null; but failure-signature-scan
# filters on `maintenance_type === "Breakdown / Corrective"` and groups by root_cause, so a fleet could
# never produce a signature, and J2's alert-led story could never be walked there. The alert lane was not
# missing a generator run - the rows it reads were missing the two fields it reads them by.
#
# ★AND THE WORDS ARE THE PLATFORM'S OWN, read from the table rather than invented: maintenance_type is one
# of "Preventive Maintenance" / "Breakdown / Corrective" / "Inspection" / "Project Work" (1,734 / 1,147 /
# 677 / 262 rows), and root_cause runs "Wear" (227), "Lubrication Failure" (136), "Contamination / Dirt",
# "Vibration / Fatigue", "Electrical Fault", "Overload". "Routine", "Component failure" and "Compliance"
# were my words for a vocabulary that already existed. Preventive work carries an EMPTY root cause here,
# which is what 2,626 rows do, rather than a made-up one.
JOBS = [
    ("Preventive Maintenance", "Engine oil and filter change at 5,000 km", "Drained oil, replaced filter, topped to spec", ""),
    ("Breakdown / Corrective", "Brake pads worn past the wear line on the front axle", "Replaced pads both sides, bled the line, road tested", "Wear"),
    ("Preventive Maintenance", "Tyre rotation and pressure check across all units", "Rotated front to rear, set to 35 psi cold", ""),
    ("Breakdown / Corrective", "Alternator not charging, battery flat by mid-route", "Replaced alternator belt and tested output at 14.2 V", "Electrical Fault"),
    ("Preventive Maintenance", "Aircon filter and refrigerant top-up before the dry season", "Cleaned filter, topped refrigerant, checked for leaks", ""),
    ("Breakdown / Corrective", "Clutch slipping on the uphill leg of the route", "Adjusted free play, scheduled plate replacement", "Wear"),
    ("Inspection", "LTO roadworthiness pre-check on the whole fleet", "Lights, brakes, emissions and body checked; two units flagged", ""),
    ("Preventive Maintenance", "Chassis lubrication and suspension check after the rains", "Greased fittings, replaced one worn bushing", ""),
]


def psql(sql: str, tries: int = 2) -> str | None:
    """Run one statement and return its ROWS - without psql's own command tag.

    ★"INSERT 0 2" IS NOT A ROW, AND IT WAS BEING READ AS ONE. `-tA` drops the header but psql still prints
    the command status after a RETURNING result, so `insert … returning name` came back as three lines:
    two vehicle names and the literal string `INSERT 0 2`. That string became a UNIT, and a logbook entry
    was written about a van called "INSERT 0 2". The same tag had been inflating every count this seeder
    printed by exactly one - "wrote 9 logbook row(s)" from a list of eight - which is why the numbers had
    always looked one too generous and nobody had a reason to check.
    """
    for _ in range(tries):
        p = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres",
                            "-d", "postgres", "-tA", "-c", sql], capture_output=True, text=True)
        if p.returncode == 0:
            lines = [l for l in p.stdout.strip().split("\n")
                     if not re.match(r"^(INSERT|UPDATE|DELETE|SELECT|COPY)\s+\d+(\s+\d+)?$", l.strip())]
            return "\n".join(lines).strip()
    return None


def q(s: str) -> str:
    return s.replace("'", "''")




def report() -> int:
    print("  %-30s %7s %7s %7s %7s" % ("hive", "assets", "logs", "pms", "seeded"))
    for f in FLEETS:
        hid = psql(f"select id from hives where name = '{q(f)}'")
        if not hid:
            print(f"  {f:<30} (not found)")
            continue
        a = psql(f"select count(*) from asset_nodes where hive_id = '{hid}'")
        l = psql(f"select count(*) from logbook where hive_id = '{hid}'")
        p = psql(f"select count(*) from pm_assets where hive_id = '{hid}'")
        s = psql(f"select count(*) from logbook where hive_id = '{hid}' and knowledge like '%{MARKER}%'")
        print("  %-30s %7s %7s %7s %7s" % (f, a, l, p, s))
    return 0


def apply(revert: bool) -> int:
    total = 0
    for f in FLEETS:
        hid = psql(f"select id from hives where name = '{q(f)}'")
        if not hid:
            print(f"  {f}: not found, skipped")
            continue
        if revert:
            n = psql(f"with d as (delete from logbook where hive_id = '{hid}' and knowledge like '%{MARKER}%' returning 1) select count(*) from d")
            # ★COMPLETIONS FIRST, BECAUSE THE SCHEDULE TAKES THEM WITH IT. pm_completions.asset_id is a
            # foreign key to pm_assets and cascades, so deleting the schedules first removed the
            # completions too - and this then reported "0 PM completion(s)" for a hive where two had just
            # been deleted. Nothing was left behind either way; the COUNT was the lie, which is the same
            # before-and-after-with-different-eyes mistake the platform has met before.
            c = psql(f"with d as (delete from pm_completions where hive_id = '{hid}' and coalesce(notes,'') like '%{MARKER}%' returning 1) select count(*) from d")
            # (*)pm_assets HAS NO `notes` COLUMN, so this delete could only ever fail - and it failed
            # SILENTLY, printing "None PM record(s)" on every revert since the tool was written, while
            # the docstring promised "the PM records those jobs close". Nothing had ever written one.
            # PM rows are now created for the vehicles THIS seeder registers, and reverted by joining back
            # to them - which must happen BEFORE the vehicles are deleted, or the join matches nothing.
            m = psql(f"with d as (delete from pm_assets where hive_id = '{hid}' and asset_name in "
                     f"(select name from asset_nodes where hive_id = '{hid}' and external_ids->>'seed' = '{MARKER}') "
                     f"returning 1) select count(*) from d")
            # ★THE LEDGER ROWS GO FIRST, OR THEY OUTLIVE THE ITEM THEY DESCRIBE. The opening-balance
            # transactions written beside each item are part of the same paired write, so a revert
            # that removed only the item would leave `inventory_transactions` rows pointing at an id
            # that no longer exists - a preservation rule on ONE side of a pair, which is the shape
            # the PM-delete above was written to fix. Deleted BEFORE the items, by the same marker.
            it = psql(f"with d as (delete from inventory_transactions where hive_id = '{hid}' "
                      f"and coalesce(note,'') like '%{MARKER}%' returning 1) select count(*) from d")
            i = psql(f"with d as (delete from inventory_items where hive_id = '{hid}' and coalesce(notes,'') like '%{MARKER}%' returning 1) select count(*) from d")
            au = psql(f"with d as (delete from hive_audit_log where hive_id = '{hid}' and meta->>'seed' = '{MARKER}' returning 1) select count(*) from d")
            # the vehicles this seeder registered for a fleet that owned none - marked in external_ids
            v = psql(f"with d as (delete from asset_nodes where hive_id = '{hid}' and external_ids->>'seed' = '{MARKER}' returning 1) select count(*) from d")
            print(f"  {f}: removed {n} logbook row(s), {m} PM record(s), {c} PM completion(s), "
                  f"{au} audit row(s), {i} inventory item(s) + {it} ledger row(s), {v} vehicle(s)")
            total += (int(n or 0) + int(m or 0) + int(i or 0) + int(v or 0)
                      + int(c or 0) + int(au or 0) + int(it or 0))
            continue
        # the units this fleet already owns are the subjects; a seeder that invents assets would be
        # writing about machines the product does not have
        # ★A FLEET THAT OWNS NO VEHICLES IS NOT A FLEET, AND THE FALLBACK MADE THAT WORSE. The rule above -
        # never invent assets - is right, and the `["Unit 1", "Unit 2"]` fallback quietly broke it from the
        # other end: Tan Delivery Vans owns ZERO asset_nodes, so its eight seeded jobs were written against
        # two units the product does not have. J1's chain (members AND assets AND a first entry) read 0
        # there, and the walk reported "the chain is empty in this hive" - correctly, about data this seeder
        # had made incoherent. A delivery-van hive needs vans. They are cloned from the shape the other two
        # fleets already use (equipment / medium / approved, with vehicle_meta), marked in `external_ids`
        # so --revert removes exactly these and nothing else, and created BEFORE the jobs so the jobs name
        # real units rather than phantoms.
        units = (psql(f"select name from asset_nodes where hive_id = '{hid}' order by created_at limit 6") or "").split("\n")
        units = [u for u in units if u.strip()]
        # ★"OWNS NONE" WAS THE WRONG THRESHOLD (2026-09-10). This block rescued a fleet with ZERO
        # vehicles and did nothing for one with two - and two is where all three fleets sat. Since the
        # history seeder writes per ASSET, a two-van fleet gets a two-van amount of history however
        # long its span, which is why `month-3` in Ramos Jeepney Line rendered a page holding one
        # logbook row. Top UP to FLEET_MIN_UNITS instead, skipping any tag the hive already owns so a
        # re-run adds only what is missing and never doubles a plate.
        if len(units) < FLEET_MIN_UNITS:
            vans = VANS.get(f) or VANS["_default"]
            have_tags = {t.strip() for t in
                         (psql(f"select tag from asset_nodes where hive_id = '{hid}' and tag is not null") or "").split("\n")
                         if t.strip()}
            have_names = {u.strip() for u in units}
            vans = [v for v in vans if v[0] not in have_tags and v[1] not in have_names]
            vans = vans[:max(0, FLEET_MIN_UNITS - len(units))]
            vrows = []
            for tag, vname, make, model, year, odo in vans:
                meta = ('{"vin": null, "make": "%s", "year": "%s", "model": "%s", "plate": "%s", '
                        '"odometer_km": %d, "insurance_expiry": null, "registration_expiry": null, '
                        '"odometer_baseline_km": %d}') % (make, year, model, tag, odo, odo)
                vrows.append("('{h}','{t}','{n}','equipment','medium','approved','{m}'::jsonb,'{{\"seed\":\"{k}\"}}'::jsonb)".format(
                    h=hid, t=q(tag), n=q(vname), m=meta, k=MARKER))
            # Nothing left to add once the fleet is already at the floor. An empty VALUES list is a SQL
            # error, and "already stocked" is the normal outcome of a re-run, not a failure.
            if not vrows:
                print(f"  {f}: already owns {len(units)} unit(s) - at or above the floor of {FLEET_MIN_UNITS}")
                added = []
            else:
                ins = psql("insert into asset_nodes (hive_id, tag, name, level, criticality, status, vehicle_meta, external_ids) values "
                           + ",".join(vrows) + " returning name")
                if ins is None:
                    print(f"  {f}: the vehicle insert did not answer - skipped rather than write jobs about phantom units")
                    continue
                added = [u for u in ins.split("\n") if u.strip()]
                # EXTEND, never replace. The fleet's existing units are still its units, and the jobs
                # below are written against this list - replacing it would hand every seeded job to the
                # new vans and leave the originals with no history at all.
                units = units + added
                print(f"  {f}: owned {len(units) - len(added)} unit(s), registered {len(added)} more "
                      f"-> {len(units)} ({', '.join(added)})")
            # and a PM schedule for each, so "the PM month" has something to be true about here too
            _pmwho = psql(f"select worker_name from hive_members where hive_id = '{hid}' and status = 'active' order by role limit 1") or 'the operator'
            _anchor = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
            # ★A SCHEDULE WITH NO TAG CANNOT BE REACHED FROM A BREAKDOWN. pm_assets.tag_id is what
            # logbook.machine is matched against - it is the bridge a supervisor's "what did skipping
            # this PM cost me" question runs across - and every other PM schedule on the platform
            # carries a plate ("NDS 8214", "FLT 0001"). These two vans were registered WITH plates on
            # their asset_nodes rows and their schedules were written without, so the vans were the
            # only assets whose PM could not be tied to a fault. The plate is copied from the asset
            # rather than invented, so both rows say the same thing about the same van.
            prows = []
            # ★ONLY THE UNITS THIS RUN REGISTERED. `units` now holds the fleet's WHOLE inventory, and a
            # vehicle that was already here already has its schedule - writing one per unit would give
            # the pre-existing vans a second PM row on every top-up. The paired-write guard further
            # down learned this lesson for the logbook; the same rule applies here.
            for u in added:
                # read the plate the vehicle was registered with; a VALUES list cannot hold a subquery,
                # and there are a handful of units, so one small read each is the plain way to do it
                plate = psql(f"select tag from asset_nodes where hive_id = '{hid}' and name = '{q(u)}' and tag is not null limit 1")
                prows.append("('{h}','{w}','{a}','Vehicle','Route depot','medium','{d}',{tg})".format(
                    h=hid, w=q(_pmwho), a=q(u), d=_anchor,
                    tg=("'" + q(plate.strip()) + "'") if (plate and plate.strip()) else "null"))
            if not prows:
                pass                      # nothing new was registered, so nothing new needs a schedule
            else:
                pins = psql("insert into pm_assets (hive_id, worker_name, asset_name, category, location, criticality, last_anchor_date, tag_id) values "
                            + ",".join(prows) + " returning id")
                if pins is None:
                    print(f"  {f}: the PM insert did not answer - the vehicles exist, their schedules do not")
                else:
                    print(f"  {f}: wrote {len([x for x in pins.splitlines() if x.strip()])} PM schedule(s)")
        who = psql(f"select worker_name from hive_members where hive_id = '{hid}' and status = 'active' order by role limit 1") or "the operator"
        # ★IDEMPOTENT MEANS CHECKED, NOT CLAIMED. The docstring promised "re-running never doubles up" and the
        # second run doubled every fleet's logbook from 8 rows to 16, because only the INVENTORY block looked
        # for the marker first. A guard that exists for one half of a paired write is not a guard.
        already = psql(f"select count(*) from logbook where hive_id = '{hid}' and knowledge like '%{MARKER}%'")
        if already is None:
            print(f"  {f}: could not ask whether it is already seeded - skipped rather than risk doubling")
            continue
        if already.isdigit() and int(already) > 0:
            print(f"  {f}: already carries {already} seeded job(s) - not writing them again")
            made = 0
        else:
            made = -1                      # -1 means "go ahead and write"
        rows = []
        now = datetime.now(timezone.utc)
        # ★A REAL FLEET'S HISTORY HAS REPEATS, AND THIS ONE HAD NONE. The eight jobs above are one of
        # each kind, cycled across the units, so no van ever comes back with the same fault twice - and a
        # maintenance history where nothing recurs is the one shape a maintenance platform is least likely
        # to see. It also meant failure-signature-scan could never fire here: its repeat_failure rule wants
        # the same machine and the same root cause three times in 90 days, and three varied breakdowns
        # spread over two vans is not a pattern. The three below are the story every jeepney operator
        # knows - one overloaded unit eating brakes - pinned to a single van so it reads as the recurrence
        # it is. The alert is a CONSEQUENCE of the history being realistic, not the reason for writing it.
        # how long a closed job stayed open, drawn from the rows that already carry closed_at:
        # median 0.5h, p90 5.4h. A fixed number would make every fleet job identical, which is its own
        # kind of false data, so this cycles through the real spread.
        CLOSE_HOURS = [0.5, 1.5, 0.75, 4.0, 2.0, 5.4, 1.0]
        RECURRING = [
            ("Breakdown / Corrective", "Front brake pads down to the backing plate again, third time this quarter",
             "Replaced pads and skimmed both discs; recommended the operator ease the loading on this unit", "Wear"),
            ("Breakdown / Corrective", "Brake judder returned under heavy braking on the descent",
             "Replaced warped front discs and pads, bedded them in on a test run", "Wear"),
            ("Breakdown / Corrective", "Brake pads worn again after six weeks on the same unit",
             "Replaced pads, checked caliper slide pins for binding - one seized, freed and greased", "Wear"),
        ]
        for j, (mtype, problem, action, cause) in enumerate(RECURRING):
            when = (now - timedelta(days=12 + j * 24)).isoformat()      # ~12, 36 and 60 days back: inside the rule's 90-day window
            rows.append("('{h}','{w}','{m}','{c}','{p}','{a}','{k}','Closed','{t}','{d}','{mt}','{rc}','{ca}')".format(
                h=hid, w=q(who), m=q(units[0]), c="Vehicle", p=q(problem), a=q(action),
                k=q(f"{MARKER}: the recurrence a fleet actually sees, on one unit"),
                t=when, d=when[:10], mt=q(mtype), rc=q(cause),
                ca=(datetime.fromisoformat(when) + timedelta(hours=CLOSE_HOURS[j % len(CLOSE_HOURS)])).isoformat()))
        for i, (mtype, problem, action, cause) in enumerate(JOBS):
            unit = units[i % len(units)]
            when = (now - timedelta(days=7 * (len(JOBS) - i) + (i % 3))).isoformat()
            # ★THE TABLE'S OWN VOCABULARY: status is one of Open/Closed/Resolved (a CHECK constraint), not
            # "Completed" - the word I brought. And `date` IS NOT NULL AND HAS NO DEFAULT. The first run wrote nothing and said so quietly
            # ("wrote 0 rows"), because the helper swallowed the constraint error - the column the product
            # actually keys its day on had to be read from the failure, not assumed from `created_at`.
            rows.append("('{h}','{w}','{m}','{c}','{p}','{a}','{k}','Closed','{t}','{d}','{mt}','{rc}','{ca}')".format(
                h=hid, w=q(who), m=q(unit), c="Vehicle", p=q(problem), a=q(action),
                k=q(f"{MARKER}: seeded so the fleet journeys have a real history to walk"),
                t=when, d=when[:10], mt=q(mtype), rc=q(cause),
                ca=(datetime.fromisoformat(when) + timedelta(hours=CLOSE_HOURS[i % len(CLOSE_HOURS)])).isoformat()))
        if made == -1:
            ins = psql("insert into logbook (hive_id, worker_name, machine, category, problem, action, knowledge, status, created_at, date, maintenance_type, root_cause, closed_at) values "
                       + ",".join(rows) + " returning id")
            if ins is None:
                print(f"  {f}: the insert did not answer (database unreachable) - nothing written")
                continue
            made = len([x for x in ins.splitlines() if x.strip()])
            print(f"  {f}: wrote {made} logbook row(s) across {len(units)} unit(s), reported by {who}")
        total += made

        # ★AND THE PARTS THOSE JOBS CONSUMED. The spare-part journey (J23: inventory -> logbook -> asset-hub
        # -> analytics) reads "parts exist and have moved" and found ZERO in every fleet - the fleets were
        # seeded with vehicles and work but nothing to fit to them, so the story could not be lived there.
        have = psql(f"select count(*) from inventory_items where hive_id = '{hid}'")
        if have is not None and have.isdigit() and int(have) == 0:
            parts = [("Engine oil filter", "FLT-OIL-15W40", 12, 4, "Filters"),
                     ("Front brake pad set", "BRK-PAD-FR", 6, 2, "Brakes"),
                     ("Alternator belt", "BLT-ALT-13X900", 4, 2, "Belts"),
                     ("Air filter element", "FLT-AIR-STD", 8, 3, "Filters"),
                     ("Wheel bearing grease 1kg", "GRS-WB-1KG", 5, 2, "Lubricants")]
            # worker_name is NOT NULL with no default - the person who keeps the shelf, read from the hive
            vals = ",".join("('{h}','{w}','{n}','{p}',{q},{m},'{c}','{k}')".format(
                h=hid, w=q(who), n=q(name), p=q(pn), q=qty, m=mn, c=q(cat),
                k=q(f"{MARKER}: parts the seeded jobs consume")) for name, pn, qty, mn, cat in parts)
            got = psql("insert into inventory_items (hive_id, worker_name, part_name, part_number, qty_on_hand, "
                       f"min_qty, category, notes) values {vals} returning id")
            n_parts = len([x for x in (got or "").split("\n") if x.strip()])
            print(f"  {f}: wrote {n_parts} inventory item(s) so the spare-part journey has something to move")
            total += n_parts

            # ★A SHELF WITHOUT AN OPENING LEDGER ROW IS A ONE-SIDED WRITE (2026-09-10). The insert
            # above sets `qty_on_hand` to a literal (12, 6, 4, 8, 5) and wrote NOTHING to
            # inventory_transactions - so the job-consumption rows added afterwards computed their
            # `qty_after` from a base of ZERO, and the shelf and its own ledger described two
            # different stock levels. Nine items ended up disagreeing and THREE banked invariants went
            # red on it: inventory__stock_conserved, __movement_leaves_row and __no_negative_stock.
            # Both halves looked right in isolation, which is exactly why nobody saw it.
            # The opening balance is part of creating the item, not a separate act: `receive` is the
            # product's own word for stock arriving, and qty_after equals what the shelf was set to.
            ids = [x.strip() for x in (got or "").split("\n") if x.strip()]
            if ids:
                ob = ",".join(
                    "('invopen-' || replace(gen_random_uuid()::text,'-',''), '{w}', '{i}', 'receive', "
                    "(select qty_on_hand from inventory_items where id = '{i}'), "
                    "(select qty_on_hand from inventory_items where id = '{i}'), "
                    "'{k}: opening stock', '{h}')".format(w=q(who), i=q(i), h=hid,
                                                          k=q(MARKER))
                    for i in ids)
                opened = psql("insert into inventory_transactions (id, worker_name, item_id, type, "
                              f"qty_change, qty_after, note, hive_id) values {ob} returning id")
                n_ob = len([x for x in (opened or "").split("\n") if x.strip()])
                print(f"  {f}: and {n_ob} opening-balance row(s), so the shelf and its ledger start level")

        # ★A THIRD AND FOURTH THING THIS FILE CLAIMED AND DID NOT DO (2026-09-08). The docstring says it
        # turns a vehicle registry into an operating fleet. Two journeys disagreed: J3 "the PM month" reads
        # least(pm_assets, pm_completions) and J4 "audit season" reads least(logbook, hive_audit_log), and
        # BOTH came back 0 in Ramos Jeepney Line and Tan Delivery Vans while their schedules and logbook
        # were full. A hive whose PMs are never closed, and whose actions leave no trail, is a registry
        # again one level up: it holds the plan and the work but nothing that says either happened.
        #
        # (a) COMPLETIONS THAT CLOSE THE SCHEDULES. Written from pm_assets itself rather than a list of
        #     names, so every completion is about a schedule that exists; asset_id is resolved through
        #     asset_nodes and left NULL when no row matches rather than pointed at a guess. `status` is
        #     left NULL because this table's allowed words have not been read from its CHECK, and a word
        #     I bring is exactly what wrote "Completed" into a logbook that only accepts Open/Closed/
        #     Resolved. The dates are spread because a daily-cap trigger guards this table.
        cdone = psql(f"select count(*) from pm_completions where hive_id = '{hid}' and coalesce(notes,'') like '%{MARKER}%'")
        if cdone is not None and cdone.isdigit() and int(cdone) == 0:
            # ★`asset_id` ON THIS TABLE IS NOT AN ASSET. Its foreign key is `pm_completions_asset_id_fkey
            # -> pm_assets`, so the column named for a machine actually points at the SCHEDULE ROW. The
            # first version joined through asset_nodes to get "the asset this PM is about", which is what
            # the name says, and every insert was refused: "Key (asset_id)=(...) is not present in table
            # pm_assets". The seeder reported "the completion insert did not answer" and moved on, because
            # psql returns None for a refusal exactly as it does for an unreachable database - the same
            # conflation this session fixed in two provers, met a third time from the writing side.
            # A completion completes a SCHEDULE, which is also the truer reading of the domain.
            # ★AND A NAME IS NOT AN IDENTITY. This wrote worker_name and left auth_uid null, so seven PM
            # completions said WHO did the work in text and could not be tied to an account - the
            # psql-probe recipe `completion_attributed` asks for exactly that ("every PM completion names
            # who did it AND what") and had 7 unattributed rows to show for it. A maintenance completion
            # is the record that a legally-required task was performed; a name nobody can resolve to a
            # person is not attribution. The uid is read from the membership this seeder already casts.
            got = psql(
                "insert into pm_completions (hive_id, worker_name, auth_uid, asset_id, completed_at, notes) "
                f"select '{hid}', '{q(who)}', "
                f"(select m.auth_uid from hive_members m where m.hive_id = '{hid}' and m.worker_name = '{q(who)}' limit 1), "
                f"p.id, now() - ((row_number() over (order by p.id)) * interval '4 days'), "
                f"'{q(MARKER)}: the completion that closes this schedule' "
                f"from pm_assets p where p.hive_id = '{hid}' returning id")
            n_done = len([x for x in (got or "").splitlines() if x.strip()])
            if got is None:
                print(f"  {f}: the completion insert did not answer - the schedules stand open")
            else:
                print(f"  {f}: wrote {n_done} PM completion(s) so 'the PM month' has a close as well as a plan")
                total += n_done

        # (b) THE AUDIT TRAIL THAT ACCOUNTS FOR ALL OF IT. Every verb below is one the product itself
        #     writes (register_asset, edit_pm_asset, edit_part - collected from the pages' own
        #     writeAuditLog calls), because an audit row in a vocabulary the viewer does not know is a row
        #     nobody can read. The marker lives in `meta->>'seed'`, which is how --revert finds them.
        adone = psql(f"select count(*) from hive_audit_log where hive_id = '{hid}' and meta->>'seed' = '{MARKER}'")
        if adone is not None and adone.isdigit() and int(adone) == 0:
            trail = [
                ("register_asset", "asset_node", "select id::text, coalesce(tag, name) from asset_nodes where hive_id = '%s' order by created_at limit 6" % hid),
                ("edit_pm_asset", "pm_asset", "select id::text, asset_name from pm_assets where hive_id = '%s' order by id limit 6" % hid),
                ("edit_part", "inventory_item", "select id::text, part_name from inventory_items where hive_id = '%s' order by id limit 6" % hid),
            ]
            arows = []
            for action, ttype, sel in trail:
                rows = (psql(sel) or "").splitlines()
                for r in rows:
                    if not r.strip() or "|" not in r:
                        continue
                    tid, tname = r.split("|", 1)
                    arows.append("('{h}','{w}','{a}','{t}','{i}','{n}','{{\"seed\":\"{k}\"}}'::jsonb)".format(
                        h=hid, w=q(who), a=action, t=ttype, i=tid.strip(), n=q(tname.strip()), k=MARKER))
            if arows:
                got = psql("insert into hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta) values "
                           + ",".join(arows) + " returning id")
                n_aud = len([x for x in (got or "").splitlines() if x.strip()])
                if got is None:
                    print(f"  {f}: the audit insert did not answer - the work stands unaccounted for")
                else:
                    print(f"  {f}: wrote {n_aud} audit row(s) so 'audit season' has a trail to follow")
                    total += n_aud
    return 0 if total or revert else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        return apply(revert=True)
    if a.apply:
        rc = apply(revert=False)
        print()
        report()
        return rc
    return report()


if __name__ == "__main__":
    sys.exit(main())
