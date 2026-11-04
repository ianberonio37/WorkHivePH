#!/usr/bin/env python3
"""group_journey_census.py - the hand-offs between the people of one scenario, measured (Wave GJ, 2026-11-04).

Ian, 2026-11-04: "add the numbers of trajectories in our trajectories roadmap ... consider the UFAI UI UX, personas, group
of personas, journey scenarios, full stack saas layers, production/founder/public pages" - and the same day: "use the
existing trajectories roadmap" and "the open trajectories are set in milestones, and at every milestone we push".

Every axis Ian named is already an axis of the cube (Wave CX: page x layer x pillar x every admitted persona) EXCEPT a
GROUP of personas. The cube asks what ONE person can tell / may do / finds wired on a page. A team meets something else
every shift: A acts, B must see it, C must not. That hand-off is the unit this census measures.

THE CELL (the cube's cell, applied to a hand-off):
  scenario    authored below (SCENARIOS) - every W3-JN archetype that names a pair, re-expressed as ordered hand-offs,
              plus the group stories the registry lacks (G-*). A hand-off is (receiving page, sender, receiver, the
              channel the receiver arrives by, what moved).
  cast        2-3 real people per scenario, RESOLVED FROM THE DATABASE (hive_members, marketplace_platform_admins,
              marketplace_sellers, service_providers, api_keys) - never typed. A scenario whose cast the database does
              not hold is REFUSED and printed with the reason. Accounts a walk mints itself (a new supervisor, an
              invited worker) are declared `minted`; the walk creates and removes them (tools/lib/walk_accounts.mjs).
  layers      the layers the sub-layer inventory applies to the receiving page (cube_census.applicable_layers)
  pillars     U, F, I per member of the cast (each member's view of the hand-off: the sender can tell it was received,
              the receiver can tell who/when/what and may act on it, a third member may or may not as the roles say);
              A once per (hand-off, layer). A machine member has no screen: F and I only.
  UX          one row per (scenario, member): that member's screens across the scenario graded by the critic deepwalk.

THE NUMBER IS DERIVED, NEVER TYPED (the BRP rule). Three floors are printed so the choice stays measured:
  F1 hand-off x member · F2 hand-off x layer · F3 hand-off x layer x pillar x member (+ A x hand-off x layer) = the pick.

THE BLOCKS (milestones, each closed by a production push): GJ_MILESTONES below is the one place they are declared.
A hand-off whose receiving page is a founder or public page belongs to M10 whatever its scenario's block; every
scenario x member UX row belongs to M11.

    python tools/group_journey_census.py            # the tables: per block, per class, per scenario, the floors
    python tools/group_journey_census.py --json     # the machine population (what the seeder reads)
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

DB = "supabase_db_workhive"
PERSONA_PILLARS = ("U", "F", "I")
LAYER_ONLY_PILLARS = ("A",)
PILLARS_OF = {"machine-client": ("F", "I")}        # no screen to read, so no U
CHANNELS = ("hub-nav", "email-push", "deep-link", "direct", "search-arrival")

# ── THE BLOCKS. Ordered by what a person loses first: the shift's hand-offs on production pages, then the record's,
# then the market's and the team's growth, then founder/public hand-offs, then the UX face.
GJ_MILESTONES = OrderedDict([
    ("M7", {"name": "the shift's hand-offs", "classes": ("production",)}),
    ("M8", {"name": "the record's hand-offs", "classes": ("production",)}),
    ("M9", {"name": "the market's and the team's growth", "classes": ("production",)}),
    ("M10", {"name": "founder and public hand-offs", "classes": ("founder", "public")}),
    ("M11", {"name": "the group's UX face", "classes": ()}),
])
GJ_WAVE = OrderedDict([("production", "GJ-PROD"), ("founder", "GJ-FND"), ("public", "GJ-PUB"), ("ux", "GJ-UX")])

PLANT = ["Baguio Textile Mills", "Manila Electronics Assembly", "Lucena Pharmaceutical Mfg.", "Batangas Refinery Maintenance"]
FLEET = ["Dela Cruz Delivery Fleet", "Tan Delivery Vans", "Ramos Jeepney Line"]

# ── THE SCENARIOS. cast: key -> (persona, need). need is what the database must hold for that member:
#   worker / supervisor   that role, active, in the home hive          leaver   a worker of the home hive (removed by the walk)
#   multi                 a worker of the home hive active in a second  sup2     a supervisor of multi's OTHER hive
#   oversight             a platform admin (marketplace_platform_admins)
#   seller / provider     a marketplace seller / service provider whose hive is NOT the home hive
#   seller-home           a member of the home hive who sells (their public profile is the receiving page)
#   buyer / client        a member of the home hive who sells nothing   foreign  a worker of another hive
#   foreign-sup           a supervisor of another hive                  machine  an enabled API key of the home hive
#   minted                an account the walk creates and removes       anon     no account
# hops: (receiving page, sender, receiver, channel, what moved). Every hop is a hand-off: sender != receiver.
SCENARIOS = [
    # ★EVERY HOP IS A DATA PATH THE PRODUCT HAS (2026-11-04, the premise check before the first walk). The first draft
    # authored hops from the archetype titles and seeded 14,102 rows on them; read against each receiving page's own
    # reads (from / rpc / channel), a third of the claims had no path at all: a breakdown does not raise an alert-hub alert
    # (alerts are failure signatures and sensor anomalies), a supervisor does not plan a worker's day (schedule_items is a
    # person's own), a PM has an owner and no assignee, the provider has no dispute reply, community has no appeal. Each
    # hop below names the mechanism it rides: logbook-feed, notify_wo_assigned (push -> logbook?status=Open),
    # notify_submission_decided (push), shift_plans (published_by), report_community_post, raise_service_objection, ...
    # A hop whose mechanism exists but may be broken stays (the F row finds it); a hop with no mechanism was rewritten.
    # ════ M7 · the shift's hand-offs (operate + maintain) ════
    {"code": "J2", "block": "M7", "stage": "operate", "where": ["Baguio Textile Mills"],
     "title": "Breakdown to close-out: two people converge on one machine and leave a record worth reading",
     "cast": OrderedDict([("w", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("logbook.html", "w", "s", "hub-nav", "the worker's breakdown entry reaches the supervisor's logbook as it lands"),
              ("logbook.html", "s", "w", "email-push", "the supervisor assigns the work order; the worker is pushed and lands on the open list"),
              ("asset-hub.html", "w", "s", "hub-nav", "the worker's closed repair is in the machine's history"),
              ("analytics.html", "w", "s", "hub-nav", "the repair counts in the supervisor's downtime and repair time"),
              ("alert-hub.html", "w", "s", "hub-nav", "a repeat of the same breakdown raises the failure-signature alert")]},
    {"code": "J3", "block": "M7", "stage": "operate", "where": ["Manila Electronics Assembly"],
     "title": "The PM month: scheduled by one, planned and done by another, counted and reported",
     "cast": OrderedDict([("w", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("pm-scheduler.html", "s", "w", "hub-nav", "the PM the supervisor scheduled is on the worker's list"),
              ("dayplanner.html", "s", "w", "hub-nav", "the PM falls due in the worker's day"),
              ("pm-scheduler.html", "w", "s", "hub-nav", "the worker's completion moves the supervisor's PM compliance"),
              ("analytics.html", "w", "s", "hub-nav", "the completion counts in the supervisor's compliance figures"),
              ("analytics-report.html", "w", "s", "hub-nav", "the completion is in the month's report")]},
    {"code": "J9", "block": "M7", "stage": "operate", "where": ["Lucena Pharmaceutical Mfg."],
     "title": "The supervisor's week: assignments, the published shift plan, moderation and approvals, each met by a worker",
     "cast": OrderedDict([("w", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("dayplanner.html", "s", "w", "hub-nav", "the work order the supervisor assigned is in the worker's day"),
              ("shift-brain.html", "s", "w", "hub-nav", "the shift plan the supervisor published is the worker's briefing"),
              ("community.html", "w", "s", "hub-nav", "the worker's post is in the supervisor's moderation view"),
              ("hive.html", "w", "s", "hub-nav", "the machine the worker submitted waits in the supervisor's approvals"),
              ("logbook.html", "s", "w", "email-push", "the supervisor's decision is pushed to the worker")]},
    {"code": "J22", "block": "M7", "stage": "maintain", "where": ["Lucena Pharmaceutical Mfg."],
     "title": "One machine's whole life: commissioned by one, worked by another, retired and still answerable",
     "cast": OrderedDict([("w", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("asset-hub.html", "s", "w", "hub-nav", "the machine the supervisor commissioned is in the worker's list"),
              ("logbook.html", "w", "s", "hub-nav", "the worker's work on it reads on the supervisor's logbook"),
              ("pm-scheduler.html", "s", "w", "hub-nav", "the PM plan the supervisor set is the worker's"),
              ("analytics.html", "w", "s", "hub-nav", "its failures and repairs in the supervisor's numbers"),
              ("audit-log.html", "w", "s", "hub-nav", "the trail names who did what across its life")]},
    {"code": "J23", "block": "M7", "stage": "operate", "where": ["Manila Electronics Assembly"],
     "title": "One spare part: received by one, issued against real work by another, traceable both ways",
     "cast": OrderedDict([("w", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("inventory.html", "s", "w", "hub-nav", "the part the supervisor received is on the worker's shelf"),
              ("logbook.html", "w", "s", "hub-nav", "the part the worker issued is on the job entry"),
              ("inventory.html", "w", "s", "hub-nav", "the issue and the return moved the count the supervisor reads"),
              ("asset-hub.html", "w", "s", "hub-nav", "the part shows in the machine's history")]},
    {"code": "J29", "block": "M7", "stage": "maintain", "where": ["Baguio Textile Mills"],
     "title": "Typhoon season: the storm work, the offline shift and the sync, between two people",
     "cast": OrderedDict([("s", ("supervisor", "supervisor")), ("w", ("worker", "worker"))]),
     "hops": [("logbook.html", "s", "w", "email-push", "the storm work order the supervisor assigned is pushed to the worker"),
              ("logbook.html", "w", "s", "hub-nav", "the worker's entries made offline sync into the supervisor's logbook"),
              ("shift-brain.html", "s", "w", "hub-nav", "the storm shift plan the supervisor published"),
              ("analytics.html", "w", "s", "hub-nav", "the week's downtime in the supervisor's account of it")]},
    {"code": "J17", "block": "M7", "stage": "maintain", "where": ["Manila Electronics Assembly", "Lucena Pharmaceutical Mfg."],
     "title": "Sensor to work order: a machine's reading becomes a person's alert and a person's job",
     "cast": OrderedDict([("m", ("machine-client", "machine")), ("w", ("worker", "worker"))]),
     "hops": [("alert-hub.html", "m", "w", "hub-nav", "the reading the machine posted raises the worker's anomaly alert"),
              ("asset-hub.html", "m", "w", "hub-nav", "the reading is on the machine's page"),
              ("index.html", "m", "w", "hub-nav", "the alert is on the worker's home")]},
    {"code": "G-SHIFT", "block": "M7", "stage": "operate", "where": ["Manila Electronics Assembly", "Batangas Refinery Maintenance"],
     "title": "The shift changes hands: the outgoing worker's open jobs, the incoming worker's briefing, the supervisor's plan",
     "cast": OrderedDict([("o", ("worker", "worker")), ("i", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("shift-brain.html", "o", "i", "hub-nav", "the outgoing worker's open jobs are carried into the handover the incoming worker reads"),
              ("shift-brain.html", "s", "i", "hub-nav", "the shift plan the supervisor published is what the incoming worker works from"),
              ("logbook.html", "o", "i", "hub-nav", "the jobs the handover names are on the incoming worker's logbook"),
              ("logbook.html", "i", "s", "hub-nav", "the incoming worker's work on a carried-over job is in the supervisor's logbook"),
              ("hive.html", "o", "i", "hub-nav", "the printed shift handover report names the incoming technician")]},
    {"code": "G-SENSOR", "block": "M7", "stage": "maintain", "where": ["Lucena Pharmaceutical Mfg.", "Manila Electronics Assembly"],
     "title": "Reading to PM: the machine's alert, the worker's acknowledgement, the supervisor's schedule",
     "cast": OrderedDict([("m", ("machine-client", "machine")), ("w", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("alert-hub.html", "m", "w", "hub-nav", "the machine's reading raises the worker's alert"),
              ("alert-hub.html", "w", "s", "hub-nav", "the worker's acknowledgement is on the supervisor's alert"),
              ("pm-scheduler.html", "s", "w", "hub-nav", "the PM the supervisor scheduled from it is on the worker's list"),
              ("logbook.html", "w", "s", "hub-nav", "the worker's job closes the alert's loop for the supervisor")]},
    {"code": "G-MULTI", "block": "M7", "stage": "operate", "where": PLANT + FLEET,
     "title": "One person in two hives: each supervisor sees only their own hive's record of them",
     "cast": OrderedDict([("c", ("worker", "multi")), ("a", ("supervisor", "supervisor")), ("b", ("supervisor", "sup2"))]),
     "hops": [("logbook.html", "c", "a", "hub-nav", "the contractor's entry in hive A is in supervisor A's logbook"),
              ("logbook.html", "c", "b", "hub-nav", "the contractor's entry in hive B is in supervisor B's, and A's is not"),
              ("logbook.html", "a", "c", "email-push", "supervisor A's work order is pushed to the contractor and opens in hive A"),
              ("pm-scheduler.html", "b", "c", "hub-nav", "supervisor B's PM is on the contractor's list only while standing in hive B"),
              ("audit-log.html", "c", "a", "hub-nav", "the contractor's changes in hive A are in A's trail and not B's")]},
    # ════ M8 · the record's hand-offs (comply + degrade + lifetime) ════
    {"code": "J4", "block": "M8", "stage": "comply", "where": ["Batangas Refinery Maintenance", "Manila Electronics Assembly"],
     "title": "Audit season: the worker's entries are the supervisor's defence in front of an inspector",
     "cast": OrderedDict([("w", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("logbook.html", "w", "s", "hub-nav", "the worker's entries are what the supervisor audits"),
              ("audit-log.html", "w", "s", "hub-nav", "the trail names the worker's changes, before and after"),
              ("asset-hub.html", "w", "s", "hub-nav", "the machine's history an inspector reads"),
              ("analytics-report.html", "w", "s", "hub-nav", "the worker's work in the report an inspector holds")]},
    {"code": "J21", "block": "M8", "stage": "comply", "where": ["Lucena Pharmaceutical Mfg.", "Manila Electronics Assembly"],
     "title": "Benchmark to decision: one hive shares, another hive reads, nobody loses their numbers",
     "cast": OrderedDict([("s", ("supervisor", "supervisor")), ("w", ("worker", "worker")), ("f", ("supervisor", "foreign-sup"))]),
     "hops": [("hive.html", "s", "w", "hub-nav", "the supervisor's opt-in is told to the hive"),
              ("ph-intelligence.html", "s", "f", "hub-nav", "the hive's contribution reaches the sector view another hive reads, anonymised"),
              ("community.html", "s", "w", "hub-nav", "the supervisor shares the decision with the hive")]},
    {"code": "J24", "block": "M8", "stage": "comply", "where": ["Batangas Refinery Maintenance", "Lucena Pharmaceutical Mfg."],
     "title": "Safety incident: the worker's lock-out becomes the supervisor's record and an inspector's trail",
     "cast": OrderedDict([("w", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("logbook.html", "w", "s", "hub-nav", "the worker's lock-out entry"),
              ("asset-hub.html", "w", "s", "hub-nav", "the machine's safety status as the supervisor reads it"),
              ("audit-log.html", "w", "s", "hub-nav", "the trail an inspector will read two years later"),
              ("analytics-report.html", "w", "s", "hub-nav", "the incident in the report")]},
    {"code": "J14", "block": "M8", "stage": "lifetime", "where": ["Manila Electronics Assembly", "Baguio Textile Mills"],
     "title": "Leaving: the supervisor removes a member, and what remains is honest to both",
     "cast": OrderedDict([("s", ("supervisor", "supervisor")), ("l", ("worker", "leaver"))]),
     "hops": [("hive.html", "s", "l", "hub-nav", "the leaver reads that they were removed and what they keep"),
              ("logbook.html", "l", "s", "hub-nav", "the leaver's entries stay, still attributed to them"),
              ("audit-log.html", "l", "s", "hub-nav", "the leaver's history stays attributed in the trail"),
              ("achievements.html", "s", "l", "hub-nav", "the leaver's own achievements stay theirs")]},
    {"code": "G-ESC", "block": "M8", "stage": "comply", "where": ["Baguio Textile Mills", "Manila Electronics Assembly"],
     "title": "A problem the supervisor cannot settle: it reaches the platform, and both are told the outcome",
     "cast": OrderedDict([("w", ("worker", "worker")), ("s", ("supervisor", "supervisor")), ("o", ("oversight", "oversight"))]),
     "hops": [("community.html", "w", "s", "hub-nav", "the worker's reported problem is in the supervisor's queue"),
              ("feedback/index.html", "o", "s", "deep-link", "the platform's decision on the supervisor's escalation is the status on the board"),
              ("feedback/index.html", "o", "w", "deep-link", "and the status the worker who reported it reads")]},
    {"code": "G-ADV", "block": "M8", "stage": "comply", "where": ["Lucena Pharmaceutical Mfg.", "Baguio Textile Mills"],
     "title": "The record reached for from outside: the hand-off stays inside its hive, refused in words",
     "cast": OrderedDict([("w", ("worker", "worker")), ("s", ("supervisor", "supervisor")), ("a", ("adversary", "foreign"))]),
     "hops": [("logbook.html", "w", "s", "hub-nav", "the worker's hand-off record reaches the supervisor"),
              ("logbook.html", "w", "a", "deep-link", "a foreign-hive member holding the record's link is refused in words"),
              ("asset-hub.html", "s", "a", "deep-link", "the supervisor's machine record is refused to the foreign member")]},
    {"code": "G-LEAVE", "block": "M8", "stage": "lifetime", "where": ["Manila Electronics Assembly", "Batangas Refinery Maintenance"],
     "title": "A member removed: their open work reassigned, their history kept, the roster honest to all three",
     "cast": OrderedDict([("s", ("supervisor", "supervisor")), ("l", ("worker", "leaver")), ("w", ("worker", "worker"))]),
     "hops": [("hive.html", "s", "l", "hub-nav", "the leaver reads that they were removed and what they keep"),
              ("logbook.html", "s", "w", "email-push", "the leaver's open work order, reassigned, is pushed to the remaining worker"),
              ("logbook.html", "l", "w", "hub-nav", "the leaver's history, still attributed, for the one who carries on"),
              ("hive.html", "s", "w", "hub-nav", "the roster the remaining worker reads no longer lists the leaver")]},
    # ════ M9 · the market's and the team's growth (trade + grow + integrate + acquire) ════
    {"code": "J1", "block": "M9", "stage": "acquire", "where": PLANT,
     "title": "Onboard to first value: a hive is born, a colleague joins, the first machine and entry are real",
     "cast": OrderedDict([("n", ("new-user", "minted")), ("i", ("new-user", "minted"))]),
     "hops": [("hive.html", "n", "i", "deep-link", "the invite the new supervisor sent lands the worker in the hive"),
              ("hive.html", "i", "n", "hub-nav", "the joiner appears on the new supervisor's roster"),
              ("asset-hub.html", "n", "i", "hub-nav", "the first machine the supervisor added is in the worker's list"),
              ("logbook.html", "i", "n", "hub-nav", "the worker's first entry is in the supervisor's logbook"),
              ("pm-scheduler.html", "n", "i", "hub-nav", "the first PM the supervisor set is the worker's")]},
    {"code": "J25", "block": "M9", "stage": "acquire", "where": ["Batangas Refinery Maintenance", "Manila Electronics Assembly"],
     "title": "New hire to trusted hand: the skill proved, the first supervised job, the record of it",
     "cast": OrderedDict([("w", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("hive.html", "w", "s", "hub-nav", "the skill the new worker proved is on the supervisor's team view"),
              ("logbook.html", "s", "w", "email-push", "the supervisor's first supervised job is pushed to the new worker"),
              ("logbook.html", "w", "s", "hub-nav", "the new worker's first job is in the supervisor's logbook")]},
    {"code": "J19", "block": "M9", "stage": "acquire", "where": ["Baguio Textile Mills", "Lucena Pharmaceutical Mfg."],
     "title": "Locked out and back to work: the supervisor lets the worker in without handing over a password",
     "cast": OrderedDict([("w", ("returner", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("index.html", "s", "w", "direct", "the worker signs in with what the supervisor reset and is told to change it"),
              ("logbook.html", "s", "w", "hub-nav", "the worker's open work is still theirs after the reset"),
              ("audit-log.html", "w", "s", "hub-nav", "the reset is in the trail with who did it")]},
    {"code": "J5", "block": "M9", "stage": "trade", "where": PLANT,
     "title": "Shortage to shelf: a part sourced from another hive, asked for, answered and reviewed",
     "cast": OrderedDict([("b", ("buyer", "buyer")), ("v", ("seller", "seller"))]),
     "hops": [("marketplace.html", "v", "b", "hub-nav", "the seller's listing is what the buyer finds"),
              ("marketplace-seller.html", "b", "v", "hub-nav", "the buyer's inquiry is in the seller's console"),
              ("marketplace.html", "v", "b", "hub-nav", "the seller's answer is on the buyer's inquiry"),
              ("marketplace-seller-profile.html", "b", "v", "hub-nav", "the buyer's review is on the seller's public profile")]},
    {"code": "J6", "block": "M9", "stage": "trade", "where": PLANT,
     "title": "Hire a specialist: the provider's listing, the client's request, the quote chosen, the review that follows",
     "cast": OrderedDict([("c", ("buyer", "client")), ("p", ("seller", "provider"))]),
     "hops": [("marketplace.html", "p", "c", "hub-nav", "the provider is what the client finds in the service catalogue"),
              ("marketplace-seller.html", "c", "p", "hub-nav", "the client's request is in the provider's open broadcasts"),
              ("marketplace.html", "p", "c", "hub-nav", "the provider's quote is on the client's request to choose"),
              ("marketplace-seller-profile.html", "c", "p", "hub-nav", "the client's review follows the provider")]},
    {"code": "J27", "block": "M9", "stage": "trade", "where": PLANT,
     "title": "A deal goes wrong: the dispute, the reply, the admin's resolution both parties can read",
     "cast": OrderedDict([("b", ("buyer", "buyer")), ("v", ("seller", "seller")), ("o", ("oversight", "oversight"))]),
     "hops": [("marketplace-seller.html", "b", "v", "hub-nav", "the buyer's dispute is in the seller's console"),
              ("marketplace.html", "v", "b", "hub-nav", "the seller's reply is on the buyer's order"),
              ("marketplace.html", "o", "b", "email-push", "the admin's resolution, read by the buyer"),
              ("marketplace-seller.html", "o", "v", "email-push", "the admin's resolution, read by the seller")]},
    {"code": "J7", "block": "M9", "stage": "grow", "where": ["Batangas Refinery Maintenance", "Manila Electronics Assembly"],
     "title": "The knowledge loop: one person's question, another's answer, accepted, and the credit it earns",
     "cast": OrderedDict([("a", ("worker", "worker")), ("r", ("worker", "worker"))]),
     "hops": [("community.html", "a", "r", "hub-nav", "the question reaches the answerer"),
              ("community.html", "r", "a", "email-push", "the answer is pushed to the asker"),
              ("community.html", "a", "r", "email-push", "the accepted answer is told to the answerer"),
              ("achievements.html", "a", "r", "hub-nav", "the credit the accepted answer earned")]},
    {"code": "J15", "block": "M9", "stage": "integrate", "where": ["Manila Electronics Assembly", "Lucena Pharmaceutical Mfg."],
     "title": "The machine client: a CMMS connects and syncs, and the supervisor can read what it did",
     "cast": OrderedDict([("m", ("machine-client", "machine")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("plant-connections.html", "m", "s", "hub-nav", "the sync status the supervisor reads"),
              ("integrations.html", "m", "s", "hub-nav", "the records the connection imported"),
              ("logbook.html", "m", "s", "hub-nav", "the synced work orders in the logbook")]},
    {"code": "J10", "block": "M9", "stage": "integrate", "where": FLEET,
     "title": "The vehicle owner's month: the owner's units and PMs, the driver's log, the cost",
     "cast": OrderedDict([("o", ("supervisor", "supervisor")), ("d", ("driver-worker", "worker"))]),
     "hops": [("asset-hub.html", "o", "d", "hub-nav", "the vehicle the owner registered is the driver's"),
              ("logbook.html", "d", "o", "hub-nav", "the driver's log reaches the owner"),
              ("pm-scheduler.html", "o", "d", "hub-nav", "the owner's PM per unit on the driver's list"),
              ("analytics.html", "d", "o", "hub-nav", "the driver's work in the owner's cost")]},
    {"code": "J30", "block": "M9", "stage": "maintain", "where": ["Manila Electronics Assembly", "Lucena Pharmaceutical Mfg."],
     "title": "Energy audit: the engineer's calculation becomes the project and the report management acts on",
     "cast": OrderedDict([("e", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("project-manager.html", "e", "s", "hub-nav", "the engineer's saved calculation is on the project the supervisor reads"),
              ("project-report.html", "e", "s", "hub-nav", "the report management acts on")]},
    {"code": "J8", "block": "M9", "stage": "maintain", "where": ["Batangas Refinery Maintenance", "Manila Electronics Assembly"],
     "title": "An engineering project: the engineer's bill of materials, the manager's change order, the progress",
     "cast": OrderedDict([("e", ("worker", "worker")), ("p", ("supervisor", "supervisor"))]),
     "hops": [("project-manager.html", "e", "p", "hub-nav", "the BOM the engineer generated is on the project"),
              ("project-manager.html", "p", "e", "hub-nav", "the change order the manager raised reaches the engineer"),
              ("project-report.html", "e", "p", "hub-nav", "the engineer's progress in the manager's report")]},
    {"code": "J12", "block": "M9", "stage": "acquire", "where": ["Baguio Textile Mills", "Lucena Pharmaceutical Mfg."],
     "title": "Stranger to member: the newcomer asks to join, the supervisor approves, the first entry is real",
     "cast": OrderedDict([("n", ("new-user", "minted")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("hive.html", "n", "s", "hub-nav", "the newcomer's join request is on the supervisor's hive page"),
              ("hive.html", "s", "n", "hub-nav", "the supervisor's approval is the newcomer's first screen"),
              ("logbook.html", "n", "s", "hub-nav", "the newcomer's first entry is in the supervisor's logbook")]},
    {"code": "J31", "block": "M9", "stage": "grow", "where": PLANT,
     "title": "The portable portfolio: what the worker chose to share, read by a stranger, and nothing more",
     "cast": OrderedDict([("w", ("seller", "seller-home")), ("x", ("anon", "anon"))]),
     "hops": [("public-feed.html", "w", "x", "deep-link", "the shared post shows only what the owner chose"),
              ("marketplace-seller-profile.html", "w", "x", "deep-link", "the public profile a stranger reads")]},
    {"code": "G-SVC", "block": "M9", "stage": "trade", "where": PLANT,
     "title": "A service job disputed and adjudicated: client, provider and admin each read the outcome",
     "cast": OrderedDict([("c", ("buyer", "client")), ("p", ("seller", "provider")), ("o", ("oversight", "oversight"))]),
     "hops": [("marketplace-seller.html", "c", "p", "hub-nav", "the client's problem report puts the job in the provider's disputed bucket"),
              ("marketplace.html", "o", "c", "email-push", "the admin's adjudication, read by the client"),
              ("marketplace-seller.html", "o", "p", "email-push", "the adjudication and its credit adjustment, read by the provider")]},
    {"code": "G-MOD", "block": "M9", "stage": "grow", "where": ["Batangas Refinery Maintenance", "Manila Electronics Assembly"],
     "title": "A post flagged and moderated: poster, flagger and supervisor each read what happened",
     "cast": OrderedDict([("p", ("worker", "worker")), ("f", ("worker", "worker")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("community.html", "f", "s", "hub-nav", "the flag is in the supervisor's moderation queue"),
              ("community.html", "s", "p", "hub-nav", "the poster reads what the supervisor did to the post"),
              ("community.html", "s", "f", "hub-nav", "the flagger reads the outcome of the flag")]},
    {"code": "G-ONB", "block": "M9", "stage": "acquire", "where": PLANT,
     "title": "A hive born and joined: each joiner's first screen is the hive, not the landing",
     "cast": OrderedDict([("n", ("new-user", "minted")), ("i", ("new-user", "minted")), ("t", ("assistive-tech", "minted"))]),
     "hops": [("hive.html", "n", "i", "deep-link", "the invite lands the first joiner in the hive"),
              ("hive.html", "n", "t", "deep-link", "the invite lands the screen-reader joiner in the hive, every control named"),
              ("hive.html", "i", "n", "hub-nav", "the joiners on the new supervisor's roster"),
              ("logbook.html", "t", "n", "hub-nav", "the screen-reader joiner's first entry in the supervisor's logbook")]},
    {"code": "G-PUBLIC", "block": "M9", "stage": "acquire", "where": ["Baguio Textile Mills", "Manila Electronics Assembly"],
     "title": "A shared result brings a stranger in: the link, the sign-up, the supervisor's approval",
     "cast": OrderedDict([("w", ("worker", "worker")), ("x", ("new-user", "minted")), ("s", ("supervisor", "supervisor"))]),
     "hops": [("tools/oee-calculator/index.html", "w", "x", "deep-link", "the shared result opens for the stranger with the numbers in it"),
              ("hive.html", "x", "s", "hub-nav", "the stranger's join request is on the supervisor's hive page"),
              ("hive.html", "s", "x", "hub-nav", "the approval is the newcomer's first screen")]},
]


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _psql(sql: str) -> list[list[str]]:
    out = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-F", "|",
                          "-v", "ON_ERROR_STOP=1"], input=sql, capture_output=True, text=True, encoding="utf-8", timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"psql failed: {out.stderr.strip()[:300]}")
    return [ln.split("|") for ln in out.stdout.splitlines() if ln.strip()]


def people() -> dict:
    """The database's own people: every active membership with the flags a cast is chosen by, and the hives that hold
    an enabled API key. Read on every run - a reseed can change who is where, and the census follows it."""
    rows = _psql("""
select w.username, w.display_name, h.name, m.role,
       exists(select 1 from marketplace_platform_admins a where a.auth_uid = w.auth_uid),
       (select count(distinct m2.hive_id) from hive_members m2 where m2.auth_uid = w.auth_uid and m2.status = 'active'),
       exists(select 1 from marketplace_sellers s where s.auth_uid = w.auth_uid),
       exists(select 1 from service_providers p where p.auth_uid = w.auth_uid),
       coalesce((select s.hive_id::text from marketplace_sellers s where s.auth_uid = w.auth_uid limit 1), ''),
       coalesce((select p.hive_id::text from service_providers p where p.auth_uid = w.auth_uid limit 1), ''),
       h.id::text
  from hive_members m join worker_profiles w on w.auth_uid = m.auth_uid join hives h on h.id = m.hive_id
 where m.status = 'active' and w.username is not null
 order by h.name, w.username;""")
    keys = {r[0] for r in _psql("select distinct h.name from api_keys k join hives h on h.id = k.hive_id where k.enabled;")}
    mem = [{"user": r[0], "name": r[1], "hive": r[2], "role": r[3], "admin": r[4] == "t", "nh": int(r[5] or 0),
            "seller": r[6] == "t", "provider": r[7] == "t", "seller_hive": r[8], "provider_hive": r[9], "hive_id": r[10]}
           for r in rows]
    return {"members": mem, "keyed_hives": keys}


def _purity(m: dict, keep: tuple = ()) -> tuple:
    """Prefer the plainest account for a plain role: an admin, a two-hive member, a seller or a provider can see or do
    more than the role the cell is about, which would make an I (may / may not) reading prove the wrong thing."""
    return (m["admin"] and "admin" not in keep, m["nh"] > 1 and "multi" not in keep,
            m["seller"] and "seller" not in keep, m["provider"] and "provider" not in keep, m["user"])


def resolve_cast(sc: dict, pp: dict) -> tuple[dict | None, str]:
    """{key: {persona, need, user, name, hive}} for the first home hive (in the scenario's order, then every other hive)
    whose people satisfy the cast, or (None, reason)."""
    mem = pp["members"]
    hives = list(dict.fromkeys(list(sc["where"]) + sorted({m["hive"] for m in mem})))
    reason = "no hive holds this cast"
    for home in hives:
        used: set[str] = set()
        cast: dict = {}
        ok = True
        for key, (persona, need) in sc["cast"].items():
            pick = None
            if need in ("minted", "anon"):
                cast[key] = {"persona": persona, "need": need, "user": need, "name": need, "hive": home if need == "minted" else ""}
                continue
            if need == "machine":
                if home in pp["keyed_hives"]:
                    cast[key] = {"persona": persona, "need": need, "user": f"api-key@{home}", "name": "an API key", "hive": home}
                    continue
                ok, reason = False, f"{home}: no enabled API key"
                break
            if need in ("worker", "leaver"):
                c = [m for m in mem if m["hive"] == home and m["role"] == "worker"]
                pick = min((m for m in c if m["user"] not in used), key=_purity, default=None)
            elif need == "supervisor":
                c = [m for m in mem if m["hive"] == home and m["role"] == "supervisor"]
                pick = min((m for m in c if m["user"] not in used), key=_purity, default=None)
            elif need == "multi":
                c = [m for m in mem if m["hive"] == home and m["role"] == "worker" and m["nh"] > 1 and not m["admin"]]
                pick = min((m for m in c if m["user"] not in used), key=lambda m: _purity(m, ("multi",)), default=None)
            elif need == "sup2":
                multi = next((v for v in cast.values() if v["need"] == "multi"), None)
                other = {m["hive"] for m in mem if multi and m["user"] == multi["user"] and m["hive"] != home}
                c = [m for m in mem if m["hive"] in other and m["role"] == "supervisor"]
                pick = min((m for m in c if m["user"] not in used), key=_purity, default=None)
            elif need == "oversight":
                # ★THE PLATFORM'S STAFF MUST NOT BELONG TO THE HIVE THEY JUDGE (2026-11-04, the first run): both admins
                # are Baguio members, so G-ESC / J27 / G-SVC cast an "oversight" who was the supervisor's own colleague,
                # and every I reading (the platform may decide, the hive may not) would have been read through a
                # member's rights. An admin who is a member of the home hive is no oversight for that scenario.
                inside = {m["user"] for m in mem if m["hive"] == home}
                c = [m for m in mem if m["admin"] and m["user"] not in inside]
                pick = min((m for m in c if m["user"] not in used), key=lambda m: _purity(m, ("admin", "multi")), default=None)
            elif need in ("seller", "provider"):
                flag, hk = need, f"{need}_hive"
                home_id = next((m["hive_id"] for m in mem if m["hive"] == home), "")
                c = [m for m in mem if m[flag] and m[hk] != home_id and m["hive"] != home]
                pick = min((m for m in c if m["user"] not in used), key=lambda m: _purity(m, (need, "multi")), default=None)
            elif need == "seller-home":
                c = [m for m in mem if m["hive"] == home and m["seller"]]
                pick = min((m for m in c if m["user"] not in used), key=lambda m: _purity(m, ("seller",)), default=None)
            elif need in ("buyer", "client"):
                c = [m for m in mem if m["hive"] == home and not m["seller"] and not m["provider"]]
                pick = min((m for m in c if m["user"] not in used),
                           key=lambda m: (m["role"] != "supervisor",) + _purity(m), default=None)
            elif need == "foreign":
                c = [m for m in mem if m["hive"] != home and m["role"] == "worker"
                     and not any(x["user"] == m["user"] and x["hive"] == home for x in mem)]
                pick = min((m for m in c if m["user"] not in used), key=_purity, default=None)
            elif need == "foreign-sup":
                c = [m for m in mem if m["hive"] != home and m["role"] == "supervisor"
                     and not any(x["user"] == m["user"] and x["hive"] == home for x in mem)]
                pick = min((m for m in c if m["user"] not in used), key=_purity, default=None)
            else:
                raise ValueError(f"{sc['code']}: unknown need {need!r}")
            if pick is None:
                ok, reason = False, f"{home}: no {need} for '{key}'"
                break
            used.add(pick["user"])
            cast[key] = {"persona": persona, "need": need, "user": pick["user"], "name": pick["name"], "hive": pick["hive"]}
        if ok:
            return cast, home
    return None, reason


def _target(r: dict):
    p = r.get("pages") or []
    return p[-1] if p else None


def have_cells(rows: list[dict]) -> set:
    """(scenario, page, layer, pillar, persona) a pair-bearing row of the same archetype already answers, persona '*' for A,
    plus every (scenario, handoff, layer, pillar, member) a GJ row already holds."""
    have: set = set()
    for r in rows:
        if r.get("status") == "descoped":
            continue
        g = r.get("gj") or {}
        if g.get("kind") == "group-journey":
            # the receiving page is part of the key: a hop rewritten at the same index must never read as answered
            have.add(("gj", g.get("scenario"), g.get("handoff"), None if g.get("cls") == "ux" else g.get("page"),
                      g.get("layer"), g.get("pillar"), g.get("member")))
            continue
        j = r.get("journey") or {}
        if not j.get("pair"):
            continue
        for u in r.get("ufai") or []:
            for L in r.get("layers") or []:
                have.add((j.get("archetype"), _target(r), L, u, r.get("persona")))
                have.add((j.get("archetype"), _target(r), L, u, "*"))
    return have


def census(rows: list[dict] | None = None) -> dict:
    import cube_census as cc
    from registry_io import load_doc
    rows = rows if rows is not None else load_doc()["trajectories"]
    classes = cc.page_classes()
    cls_of = {p: c for c, ps in classes.items() for p in ps}
    layers = cc.applicable_layers(classes)
    pp = people()
    have = have_cells(rows)
    scen_out, refused, cells, ux = [], [], [], []
    floors = Counter()
    for sc in SCENARIOS:
        bad = [h[0] for h in sc["hops"] if h[0] not in cls_of]
        if bad:
            refused.append({"code": sc["code"], "reason": f"not a served page: {', '.join(bad)}"})
            continue
        for h in sc["hops"]:
            assert h[1] != h[2] and h[1] in sc["cast"] and h[2] in sc["cast"] and h[3] in CHANNELS, (sc["code"], h)
        cast, home = resolve_cast(sc, pp)
        if cast is None:
            refused.append({"code": sc["code"], "reason": home})
            continue
        n_cells = 0
        for hi, (page, snd, rcv, ch, what) in enumerate(sc["hops"], start=1):
            cls = cls_of[page]
            block = sc["block"] if cls == "production" else "M10"
            floors["F1"] += len(cast)
            floors["F2"] += len(layers.get(page, []))
            base = {"scenario": sc["code"], "handoff": hi, "page": page, "cls": cls, "block": block, "sender": snd,
                    "receiver": rcv, "channel": ch, "what": what}
            for L in layers.get(page, []):
                for u in LAYER_ONLY_PILLARS:
                    if ("gj", sc["code"], hi, page, L, u, None) in have or (sc["code"], page, L, u, "*") in have:
                        floors["have"] += 1
                        continue
                    cells.append(dict(base, layer=L, pillar=u, member=None, persona=None))
                    n_cells += 1
                for mk, m in cast.items():
                    for u in PILLARS_OF.get(m["persona"], PERSONA_PILLARS):
                        if ("gj", sc["code"], hi, page, L, u, mk) in have or (sc["code"], page, L, u, m["persona"]) in have:
                            floors["have"] += 1
                            continue
                        cells.append(dict(base, layer=L, pillar=u, member=mk, persona=m["persona"]))
                        n_cells += 1
        for mk, m in cast.items():
            if ("gj", sc["code"], 0, None, None, "UX", mk) in have:
                continue
            ux.append({"scenario": sc["code"], "member": mk, "persona": m["persona"], "block": "M11",
                       "pages": list(dict.fromkeys(h[0] for h in sc["hops"] if mk in (h[1], h[2])))})
        scen_out.append({"code": sc["code"], "block": sc["block"], "stage": sc["stage"], "title": sc["title"], "home": home,
                         "cast": cast, "hops": [list(h) for h in sc["hops"]], "cells": n_cells})
    by_block = Counter(c["block"] for c in cells) + Counter(u["block"] for u in ux)
    by_class = Counter(c["cls"] for c in cells)
    return {"scenarios": scen_out, "refused": refused, "cells": cells, "ux": ux,
            "floors": {"F1 hand-off x member": floors["F1"], "F2 hand-off x layer": floors["F2"],
                       "F3 hand-off x layer x pillar x member (+A)": len(cells) + floors["have"]},
            "already_answered": floors["have"], "by_block": dict(sorted(by_block.items(), key=lambda kv: int(kv[0][1:]))),
            "by_class": dict(by_class), "total_rows": len(cells), "total_ux": len(ux),
            "handoffs": sum(len(s["hops"]) for s in scen_out), "walks": len(scen_out)}


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit the machine population")
    a = ap.parse_args()
    c = census()
    if a.json:
        print(json.dumps(c, indent=1, ensure_ascii=False))
        return 0
    print("\nGROUP JOURNEYS - the hand-offs between the people of one scenario, measured (never typed)")
    print("=" * 108)
    print(f"  {'scenario':<9} {'block':<5} {'stage':<9} {'home hive':<31} {'hand-offs':>9} {'cells':>6}   cast")
    for s in c["scenarios"]:
        cast = " · ".join(f"{k}={v['persona']}:{v['user']}" for k, v in s["cast"].items())
        print(f"  {s['code']:<9} {s['block']:<5} {s['stage']:<9} {s['home'][:31]:<31} {len(s['hops']):>9} {s['cells']:>6}   {cast}")
    for r in c["refused"]:
        print(f"  REFUSED {r['code']}: {r['reason']}")
    print(f"\n  {c['walks']} scenario walks · {c['handoffs']} hand-offs")
    print("  floors: " + " · ".join(f"{k} = {v}" for k, v in c["floors"].items()))
    print(f"  already answered by a pair-bearing row or a seeded GJ row: {c['already_answered']}")
    print("  by class  " + " · ".join(f"{k} {v}" for k, v in c["by_class"].items()) + f" · UX {c['total_ux']}")
    print("  by block  " + " · ".join(f"{k} ({GJ_MILESTONES[k]['name']}) {v}" for k, v in c["by_block"].items()))
    print(f"  = {c['total_rows']} hand-off rows + {c['total_ux']} UX rows = {c['total_rows'] + c['total_ux']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
