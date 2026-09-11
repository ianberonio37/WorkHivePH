#!/usr/bin/env python3
"""seed_expansion_wave3.py — EXPANSION WAVE 3 (2026-09-07), nine directions seeded as one change so the
denominator moves once and the header is honest from the first day.

Ian: "let us now extend the numbers of our trajectories, I want you to determine first" -> then "add also
the trajectories for full journeys, diverse, for my platform" -> then "we still have to expand and extend
the journeys". So the largest direction here is W3-JN: 32 journey ARCHETYPES cast in the platform's own
people, in four tiers, each row a WHOLE STORY across >=4 pages and >=3 layers (tier D: >=8 pages, >=5
layers, >=3 moments).

THE CAST IS THE PLATFORM'S OWN, READ FROM THE DATABASE, NOT INVENTED. The six seeded hives are Manila
Electronics Assembly, Lucena Pharmaceutical Mfg., Baguio Textile Mills, Dela Cruz Delivery Fleet, Ramos
Jeepney Line and Tan Delivery Vans; the registry before this wave had 1 electronics row, 0 textile and a
handful of pharma against 307 vehicle rows. A journey cast in a vertical the platform does not host is a
journey nobody can walk.

THE ROSTERS ARE MEASURED, THEN FROZEN (the wave-2 lesson, ★×16). The learn/calculator/page rosters are
computed from the registry as it stands BEFORE the wave; once any W3 row exists, plan() REPLAYS the
seeded rows verbatim, because every deficit this file measures shrinks the moment the wave is written and
tools/validate_trajectory_registry.py re-runs plan() to derive its expected ids.

  python tools/seed_expansion_wave3.py --dry-run   # the per-code table, the JN tier table, sample rows
  python tools/seed_expansion_wave3.py             # write (idempotent on title+pages)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/ importable for critic_seed_missing

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"
PREFIX = "W3"

# ── the platform's own people (hives read from the local database 2026-09-07; see the docstring) ──
PLANT = ["Manila Electronics Assembly", "Lucena Pharmaceutical Mfg.", "Baguio Textile Mills"]
FLEET = ["Dela Cruz Delivery Fleet", "Ramos Jeepney Line", "Tan Delivery Vans"]
HIVES = PLANT + FLEET
SOLO = ["a solo technician with no hive", "a solo rider with no hive"]
PAIRS = [(PLANT[0], PLANT[1]), (PLANT[2], FLEET[0]), (FLEET[2], SOLO[0])]
MULTI = [(PLANT[0], PLANT[1]), (FLEET[0], FLEET[2])]
PLATFORM = ["the platform itself (founder view)"]
PUBLIC_ENTRIES = [("search-arrival", "a search result for a learn article"),
                  ("direct", "a free calculator someone linked"),
                  ("qr-print", "a QR poster on a plant wall")]

NOT_A_DESTINATION = {"design-system.html", "symbol-gallery.html", "validator-catalog.html",
                     "promo-poster.html", "offline-fallback.html", "terms.html", "architecture.html"}
PUBLIC_PAGES = ["index.html", "marketplace.html", "public-feed.html", "status.html",
                "marketplace-seller-profile.html", "ph-intelligence.html", "project-report.html",
                "learn/index.html", "community.html", "achievements.html", "resume.html",
                "engineering-design.html"]
PRINT_PAGES = ["status.html", "analytics.html", "dayplanner.html", "pm-scheduler.html",
               "alert-hub.html", "project-report.html", "analytics-report.html", "skillmatrix.html"]
LAYER_SET = ["F", "D", "A", "CA", "AU", "AV", "C", "S", "H", "L", "LB", "RL", "CI"]

A_CALC = "tools/oee-calculator/index.html"
A_CALC2 = "tools/mtbf-calculator/index.html"
A_CALC3 = "tools/load-estimation-calculator/index.html"
A_LEARN = "learn/best-free-cmms-software-philippines/index.html"
A_LEARN2 = "learn/ra-11285-energy-efficiency-plant-checklist/index.html"


# ══ W3-JN · the 32 journey archetypes ══════════════════════════════════════════════════════════════
# scope: all=the six hives · plant=the three plants · fleet=the three fleets · pair=three two-sided
# castings · solo=the two hive-less people · public=three arrivals · platform=the founder · multi=two
# multi-hive castings · replay=the degraded re-walk of three daily archetypes.
# Each entry is (code, stage, scope, title, pages(ordered path), layers, ufai, persona, pair, entry,
# functions, what the person is trying to get done).
ARCHETYPES = [
    # ── acquire & onboard ──
    ("J1", "acquire", "all", "Onboard to first value: a hive exists, a colleague joins, the first machine and the first entry are real",
     ["index.html", "hive.html", "asset-hub.html", "logbook.html", "pm-scheduler.html", "alert-hub.html"],
     ["F", "D", "AU"], ["F", "U"], "new-user", "new supervisor x invited worker", "direct", [],
     "somebody who signed up an hour ago and has to have something worth showing by the end of the shift"),
    ("J11", "acquire", "solo", "Alone, then not: a person with no hive runs their own maintenance, then grows into one",
     ["index.html", "asset-hub.html", "logbook.html", A_CALC, "learn/index.html", "hive.html"],
     ["F", "D", "AU"], ["F", "U"], "solo-owner", "", "direct", [],
     "one person keeping their own machines, who later needs a second pair of hands in the same records"),
    ("J12", "acquire", "public", "Stranger to member: an arrival reads, computes, signs in and files a first entry",
     [A_LEARN, A_CALC2, "index.html", "hive.html", "logbook.html"],
     ["H", "F", "AU"], ["U", "F"], "anon", "anon -> worker", "search-arrival", [],
     "someone who has never heard of the platform and must reach real value without being asked to commit first"),
    ("J25", "acquire", "all", "New hire to trusted hand: skills declared, first supervised work, the badge that says so",
     ["hive.html", "skillmatrix.html", "logbook.html", "achievements.html", "community.html"],
     ["F", "D", "CA"], ["U", "F"], "new-user", "worker x supervisor", "hub-nav", [],
     "a new technician on their first week, and the supervisor who has to know what they can be trusted with"),
    ("J19", "acquire", "all", "Locked out and back to work: a failed sign-in, a reset that arrives, and the day continues",
     ["index.html", "hive.html", "logbook.html", "audit-log.html"],
     ["AU", "AV", "S"], ["I", "F"], "returner", "worker x supervisor", "email-push",
     ["login", "supervisor-reset-password"],
     "a worker who cannot get in at 6am, and the supervisor who can let them in without handing over a password"),
    # ── operate daily ──
    ("J2", "operate", "all", "Breakdown to close-out: the alert, the machine's history, the repair, the record, the next PM",
     ["alert-hub.html", "asset-hub.html", "shift-brain.html", "logbook.html", "pm-scheduler.html", "analytics.html"],
     ["F", "D", "A"], ["F", "U"], "worker", "worker x supervisor", "hub-nav", [],
     "a line is down and two people have to converge on the same machine, fix it and leave a record worth reading"),
    ("J3", "operate", "all", "The PM month: scheduled, planned into days, completed, counted, reported and sent",
     ["pm-scheduler.html", "dayplanner.html", "logbook.html", "analytics-report.html", "report-sender.html"],
     ["F", "D", "C"], ["F", "A"], "worker", "worker x supervisor", "hub-nav", ["send-report-email"],
     "the maintenance month as management sees it, from the schedule to the e-mail that closes it"),
    ("J13", "operate", "all", "The AI-assisted day: asked on the floor, spoken into the phone, written back with provenance",
     ["assistant.html", "voice-journal.html", "logbook.html", "audit-log.html", "analytics.html"],
     ["A", "AV", "F"], ["I", "U"], "worker", "", "hub-nav", ["voice-logbook-entry", "ai-gateway"],
     "a technician using the companion all day, whose records must still say which words were the machine's"),
    ("J9", "operate", "all", "The supervisor's week: the day plan, the handover, the approvals, the moderation, the numbers",
     ["dayplanner.html", "shift-brain.html", "community.html", "analytics.html", "ph-intelligence.html", "hive.html"],
     ["F", "D", "L"], ["U", "F"], "fleet-supervisor", "supervisor x oversight", "hub-nav", [],
     "the person accountable for other people's work, whose week is five surfaces and one story"),
    ("J26", "operate", "multi", "Two hives, one person: a day that crosses a boundary and never leaks across it",
     ["hive.html", "logbook.html", "pm-scheduler.html", "alert-hub.html"],
     ["AU", "S", "D"], ["I", "A"], "worker", "", "hub-nav", [],
     "a contractor who works for two plants and must never see one's data while standing in the other"),
    ("J24", "operate", "plant", "Safety incident: the lock-out, the record, the alert, the trail an inspector will read",
     ["logbook.html", "asset-hub.html", "alert-hub.html", "audit-log.html", "analytics-report.html"],
     ["D", "L", "F"], ["I", "F"], "worker", "worker x supervisor", "hub-nav", [],
     "the shift where something nearly went wrong and the record has to survive an inspection two years later"),
    ("J23", "operate", "all", "One spare part: received, issued against real work, returned, and paid for in the numbers",
     ["inventory.html", "logbook.html", "asset-hub.html", "analytics.html"],
     ["D", "F"], ["F", "A"], "worker", "worker x supervisor", "hub-nav", [],
     "the part that leaves the shelf for a job and has to be traceable back to it"),
    ("J20", "operate", "all", "The brief arrives and something happens: the morning digest, the alert, the day re-planned",
     ["alert-hub.html", "logbook.html", "dayplanner.html", "analytics.html"],
     ["A", "C", "D"], ["A", "F"], "fleet-supervisor", "", "email-push",
     ["scheduled-agents", "amc-orchestrator", "notify-push"],
     "the supervisor who reads one e-mail at 6am and whose day is decided by whether it was true"),
    # ── maintain & improve ──
    ("J17", "maintain", "plant", "Sensor to work order: a reading becomes an anomaly, an alert, a look, a job",
     ["alert-hub.html", "asset-hub.html", "logbook.html", "pm-scheduler.html"],
     ["AV", "D", "A"], ["F", "A"], "machine-client", "machine x worker", "direct",
     ["sensor-readings-ingest", "batch-risk-scoring"],
     "the chain that turns a number nobody watched into work somebody does"),
    ("J18", "maintain", "plant", "Predicted risk re-plans the month: the score moves the schedule, and the schedule moves the day",
     ["asset-hub.html", "pm-scheduler.html", "dayplanner.html", "analytics.html"],
     ["AV", "D"], ["F", "A"], "fleet-supervisor", "", "hub-nav",
     ["batch-risk-scoring", "weibull-fitter", "trigger-ml-retrain"],
     "the supervisor deciding what to service first, from a model they did not build"),
    ("J22", "maintain", "plant", "One machine's whole life: commissioned, worked, analysed, retired, and still answerable",
     ["asset-hub.html", "logbook.html", "pm-scheduler.html", "analytics.html", "audit-log.html"],
     ["D", "L"], ["F", "I"], "worker", "worker x supervisor", "hub-nav",
     ["asset-brain-query", "failure-signature-scan"],
     "the pump that arrived new and left as scrap, whose history has to survive both events"),
    ("J30", "maintain", "plant", "Energy audit: an article, a calculation, a design, a project, a report management can act on",
     [A_LEARN2, A_CALC3, "engineering-design.html", "project-manager.html", "project-report.html", "report-sender.html"],
     ["F", "D"], ["F", "U"], "solo-owner", "engineer x supervisor", "search-arrival",
     ["pf-calculator", "engineering-calc-agent"],
     "the RA 11285 obligation, walked from the reading that explains it to the report that discharges it"),
    ("J8", "maintain", "plant", "An engineering project: the calculation, the bill of materials, the change order, the progress",
     ["engineering-design.html", "project-manager.html", "project-report.html", "analytics.html"],
     ["D", "F"], ["F", "I"], "solo-owner", "engineer x project manager", "hub-nav",
     ["engineering-bom-sow", "project-orchestrator", "project-progress"],
     "the capital job that starts as a number and has to end as a defensible spend"),
    ("J29", "maintain", "plant", "Typhoon season: the advisory, the re-plan, the offline shift, the sync, the account of it",
     ["alert-hub.html", "dayplanner.html", "logbook.html", "analytics.html", "report-sender.html"],
     ["C", "A", "H"], ["A", "F"], "worker", "supervisor x worker", "hub-nav", [],
     "the week the power and the network both went, and the work still had to be recorded"),
    # ── comply & report ──
    ("J4", "comply", "all", "Audit season: the entries, the trail, the report, the PDF an inspector holds",
     ["logbook.html", "audit-log.html", "analytics-report.html", "report-sender.html", "project-report.html"],
     ["L", "D", "S"], ["I", "F"], "fleet-supervisor", "supervisor x oversight", "hub-nav", ["send-report-email"],
     "the DOLE or ISO visit, where the platform's memory is the defence"),
    ("J32", "comply", "platform", "The founder's month-end: the queue waiting, the actions taken, the board, and the AI's own bill of health",
     # The declared path listed six oversight surfaces in a row and FIVE of its hops followed no link the
     # platform offers - because it was written around founder-console.html, which is RETIRED. That page
     # keeps its full markup under a fixed overlay reading "The Founder Console has moved to Grafana ...
     # Approve / verify / resolve actions moved to the Platform Actions page", precisely so the ~35 static
     # validators that scan it keep passing, which is also why reading its source makes it look alive. A
     # journey must not start at a page whose only content is a redirect notice, and the title said "the
     # console" for a console that no longer exists. This is the month-end a founder can actually walk on
     # the live platform, hop by hop, every link verified: the moderation queue, the governance actions,
     # home, the board, the AI's own bill of health.
     # ...and marketplace-admin is retired too. FOUR pages went in that arc - founder-console,
     # marketplace-admin, llm-observability, agentic-rag-observability - which is most of what this
     # journey named. Every page below is live, and every hop is a link the platform really offers.
     ["platform-actions.html", "index.html", "hive.html", "ai-quality.html"],
     ["L", "RL", "CI"], ["I", "A"], "oversight", "", "hub-nav", [],
     "the person answerable for the whole platform, closing a month across six oversight surfaces"),
    ("J21", "comply", "plant", "Benchmark to decision: the hive opts in, the sector answers, and somebody changes what they do",
     ["hive.html", "ph-intelligence.html", "analytics.html", "community.html"],
     ["D", "S", "CA"], ["I", "A"], "fleet-supervisor", "supervisor x oversight", "hub-nav", ["benchmark-compute"],
     "the plant that shares its numbers to learn where it stands, and must not lose them by sharing"),
    # ── trade ──
    ("J5", "trade", "pair", "Shortage to shelf: a part runs low, is sourced from another hive, reserved, paid and received",
     ["inventory.html", "marketplace.html", "marketplace-seller.html", "marketplace-seller-profile.html"],
     ["D", "S", "F"], ["F", "I"], "buyer", "buyer x seller", "hub-nav", [],
     "two hives that never meet, trading a bearing through the platform's word"),
    ("J6", "trade", "pair", "Hire a specialist: the listing, the hail, the acceptance, the arrival, the review that follows them",
     ["marketplace.html", "marketplace-seller-profile.html", "public-feed.html", "community.html", "marketplace-seller.html"],
     ["RL", "D", "F"], ["F", "U"], "buyer", "client x provider (publisher x watcher)", "search-arrival", [],
     "the plant that needs a vibration analyst tomorrow, and the analyst whose living depends on being findable"),
    ("J27", "trade", "pair", "A deal goes wrong: the dispute, the admin's view, the resolution both parties can read",
     ["marketplace.html", "marketplace-seller-profile.html", "marketplace-admin.html", "audit-log.html"],
     ["S", "D", "L"], ["I", "F"], "buyer", "buyer x seller x admin", "hub-nav", [],
     "the transaction that failed, where the platform's fairness is the product"),
    ("J28", "trade", "all", "Money in, money spent: a GCash receipt becomes credits, a reservation, and a line in the spend",
     ["marketplace.html", "marketplace-seller.html", "analytics.html", "audit-log.html"],
     ["D", "S"], ["I", "F"], "buyer", "", "hub-nav", ["gcash-receipt-inbound", "gcash-receipt-ocr"],
     "the small plant that pays in pesos through a phone and needs the platform's arithmetic to match the bank's"),
    # ── grow ──
    ("J7", "grow", "all", "The knowledge loop: a question, the answer that solved it, the skill it proves, the feed that spreads it",
     ["community.html", "skillmatrix.html", "achievements.html", "public-feed.html", "logbook.html"],
     ["F", "D", "CA"], ["U", "F"], "worker", "asker x answerer", "hub-nav", [],
     "the platform's whole reason to have a community: one person's fix becoming everyone's"),
    ("J31", "grow", "solo", "The portable portfolio: the resume uploaded, read by a machine, polished, exported, seen by a stranger",
     ["resume.html", "public-feed.html", "index.html", "achievements.html", "marketplace-seller-profile.html"],
     ["D", "S", "F"], ["I", "U"], "solo-owner", "worker -> anon", "hub-nav", ["resume-extract", "resume-polish"],
     "the Filipino engineer applying abroad, whose record has to travel and reveal only what they chose"),
    # ── integrate & scale ──
    ("J15", "integrate", "plant", "The machine client: a CMMS connects, syncs, is told what completed, and leaves a trail",
     ["plant-connections.html", "integrations.html", "audit-log.html", "logbook.html"],
     ["A", "S", "L"], ["I", "A"], "machine-client", "integration x supervisor", "direct",
     ["cmms-sync", "cmms-webhook-receiver", "cmms-push-completion"],
     "the plant that already owns SAP or Maximo and will not run two systems by hand"),
    ("J10", "integrate", "fleet", "The vehicle owner's month: the documents read, the PMs per unit, the driver's log, the receipts, the cost",
     ["integrations.html", "asset-hub.html", "pm-scheduler.html", "logbook.html", "analytics.html"],
     ["D", "AV", "F"], ["F", "A"], "solo-owner", "fleet owner x driver", "hub-nav",
     ["vehicle-doc-extract", "gcash-receipt-ocr"],
     "the jeepney or van operator whose maintenance is a stack of paper until the platform reads it"),
    # ── degrade & leave ──
    ("J16", "degrade", "replay", "The same day, degraded: the journey re-walked on a bad network, with a dependency down, and through a release",
     ["alert-hub.html", "logbook.html", "pm-scheduler.html", "analytics.html"],
     ["H", "A", "AV"], ["A", "F"], "worker", "", "hub-nav", [],
     "the ordinary day that has to survive the conditions a Philippine plant actually has"),
    ("J14", "degrade", "all", "Leaving: a person is removed, takes their record with them, and what remains is honest to everyone",
     ["hive.html", "audit-log.html", "logbook.html", "public-feed.html", "achievements.html"],
     ["S", "AU", "L"], ["I", "F"], "adversary", "supervisor x leaver", "hub-nav", ["export-hive-data"],
     "the end of the relationship, where the Data Privacy Act and the hive's memory pull in opposite directions"),
]
REPLAY_BASES = ["J2", "J3", "J13"]          # the three daily journeys J16 re-walks
CONDITIONS = [("offline-3g", "on a 3G connection that keeps dropping"),
              ("dependency-down", "with one dependency (the AI gateway / storage / mail) refusing"),
              ("release-mid-way", "while a new release lands under them mid-journey")]
MOMENTS = [("month-3", "three months in, when the novelty is gone and the data is not"),
           ("year-2", "in year two, with a year of history behind every screen")]
OVERLAY_ENTRIES = [("deep-link", "arriving from a link somebody pasted in a chat"),
                   ("email-push", "arriving from the notification that told them to")]
ASSISTIVE = [("screen-reader", "narrow-320", "a person who hears this journey rather than sees it"),
             ("keyboard-only", "desktop-1280", "a person who walks this journey without a mouse")]
WIDE = [("tablet-768", "on a shared tablet passed around the shift"),
        ("fixed-kiosk-print", "on a wall display or a printout, unattended")]
TABLET_ARCHES = ["J3", "J9", "J20", "J24", "J4", "J2", "J23", "J18"]

# ── what the nav offers, and who links to whom. READ from nav-hub.js and the pages themselves, never
# typed here: check_journey_paths.py already derives both for the gate that judges these paths, and a
# second copy is a second thing to drift (the rule that keeps the seeder and its gate in agreement).
try:
    from check_journey_paths import hub_offered_and_parented as _hub_op, link_graph as _link_graph
    _NAV_OFFERED, _HUB_PARENTS = _hub_op()
    _LINKS = _link_graph()   # RAW, exactly what prove_full_journeys.mjs reads - see _real_parents
except Exception:                       # a missing helper must not silently drop the repair
    _NAV_OFFERED, _HUB_PARENTS, _LINKS = set(), {}, {}


def _parents_of(page: str) -> list:
    """Who the platform says this page is reached from - THE SAME ANSWER prove_full_journeys.mjs gives.

    The hub's own sentence first ("hidden, surfaced via the 'Audit Log' button on hive.html") because a
    platform naming its own route is authoritative. Otherwise every page that links here, MINUS
    index.html: the landing page links to everything and so distinguishes nothing, which is why the
    prover drops it unless it is the only linker. Getting this wrong cost a walk - the repair routed
    index.html -> achievements.html on a link that genuinely exists, and the prover still called it
    skipping the intended route, because for it achievements has exactly one parent: skillmatrix.
    A repair judged by a different rule than the prover is a repair that gets re-walked for nothing.
    """
    said = _HUB_PARENTS.get(page)
    if said:
        return [said]
    linkers = sorted(src for src, dests in _LINKS.items()
                     if page in dests and src != page and not src.startswith("learn/"))
    return [l for l in linkers if l != "index.html"] or linkers


def _hop_ok(prev: str, page: str) -> bool:
    """Can a person standing on `prev` get to `page` the way the platform intends?"""
    return page in _NAV_OFFERED or prev in _parents_of(page)


def _pick_parent(page: str, prev: str, sofar: list):
    """Which parent to route through - a decision, not an alphabetical accident.

    A page can have several honest parents (resume.html is linked from achievements, skillmatrix, two
    learn articles and, from inside a script, index). Preference order:
      1. one the story has ALREADY visited - re-entering through a room the person knows is the most
         coherent route a lifetime can take, and it adds no new surface to the path;
      2. one the nav itself offers, so the hop is reachable from anywhere;
      3. anything left that is a real app page.
    `learn/` pages are never parents here: they are the public funnel, not a place a signed-in
    person's career story doubles back through.
    """
    cands = [q for q in _parents_of(page)
             if q != prev and q != page and not q.startswith("learn/")]
    if not cands:
        return None
    for q in cands:
        if q in sofar:
            return q
    for q in cands:
        if q in _NAV_OFFERED:
            return q
    return cands[0]


def _entry_chain(page: str, prev: str, sofar: list) -> list:
    """The hops needed so `page` is entered the way the platform parents it - the WHOLE way up.

    ★INSERTING ONE PARENT JUST MOVES THE PROBLEM (2026-09-10). Routing resume.html through
    achievements.html cleared the resume complaint and the next walk returned "achievements.html is
    reached from skillmatrix.html" - achievements is itself nav-hidden and parented by exactly one
    page. Parenting is a CHAIN, not a single link, so the repair climbs until it reaches something the
    nav offers or something the previous page already links to. Bounded at three hops: a route needing
    four is a wayfinding defect to fix in the product, not a path to paper over here.
    """
    chain: list = []
    target = page
    for _ in range(3):
        parent = _pick_parent(target, prev, sofar)
        if not parent or parent in chain:
            break
        chain.insert(0, parent)
        if _hop_ok(prev, parent):        # the person can get to this parent from where they stand
            break
        target = parent
    return chain


# tier D — the whole lifetimes: (title, the archetypes it chains, the cast, pages beyond the chain)
LIFETIMES = (
    [(f"One hive's whole year: {h} from its first day to its first departure",
      ["J1", "J3", "J2", "J4", "J21", "J14"], h) for h in HIVES]
    + [(f"One worker's career: joined, worked, taught, and carried it away - {h}",
        ["J25", "J13", "J7", "J31"], h) for h in [PLANT[0], PLANT[1], FLEET[0]]]
    + [(f"One machine's lifetime, sensor to scrap - {h}", ["J22", "J17", "J18"], h) for h in PLANT]
    + [("One part's lifecycle: bought, shelved, issued, re-ordered, paid for", ["J23", "J5", "J28"], PLANT[0]),
       ("One listing's lifecycle: published, hired, disputed, resolved", ["J6", "J27"], FLEET[0]),
       ("One project's lifecycle: calculated, scoped, changed, delivered", ["J30", "J8"], PLANT[2]),
       ("One vehicle's year: papers, PMs, breakdowns, receipts, cost per kilometre", ["J10"], FLEET[1])]
)

# ══ the other eight directions ═════════════════════════════════════════════════════════════════════
LN_LENSES = {
    "F": ("The tool this article sends you to opens, and does the job the article promised", ["F", "D"]),
    "A": ("This article reads on a phone, survives being opened offline, and prints without losing its point", ["H", "F"]),
    "I": ("Every claim here is sourced and dated, and the page says in both languages how fresh it is", ["L", "F"]),
}
CL_LENSES = {
    "F": ("The platform must reproduce this calculator's reference answer from the standard it cites", ["F", "D"]),
    "A": ("The platform must let this calculation be done on a phone, offline, and carried away as a PDF", ["H", "F"]),
    "I": ("The platform must name the standard and clause behind every constant, and refuse an out-of-range input legibly", ["L", "S"]),
}
FN_LENSES = [
    ("I", "The platform must refuse this function to a caller who is not entitled to it, in the caller's own words", ["S", "AU"], "contract"),
    ("A", "The platform must degrade legibly when this function's dependency is down - never a silent success", ["A", "RL"], "contract"),
    ("F", "The platform must complete this function's documented job and persist exactly what it says it persisted", ["D", "A"], "contract"),
]
SC_LENSES = [
    ("U", "This shared piece says the same thing on every page that carries it", ["F"]),
    ("F", "This shared piece does its job on every page that carries it, not only the one it was written for", ["F", "D"]),
    ("A", "This shared piece holds up on a phone, offline, and on a wall display", ["H", "F"]),
    ("I", "This shared piece never shows one person another person's state", ["S", "F"]),
]
PG_CELLS = [
    ("new-user", "phone-390", "hub-nav", ["F"], "It is your first time on this page and nobody is beside you"),
    ("returner", "phone-390", "direct", ["AU", "F"], "You are back after weeks and this page has to show you where you left off"),
    ("worker", "tablet-768", "hub-nav", ["F"], "On a shared tablet at 768 this page has to hold together in both orientations"),
    ("anon", "phone-390", "search-arrival", ["H", "S"], "You arrived from a search result and this page must be worth the visit before you sign in"),
    ("any", "phone-390", "deep-link", ["F", "H"], "You opened this page from a pasted link with no history behind you"),
    ("machine-client", "fixed-kiosk-print", "qr-print", ["F"], "This page is on a wall or a printout and must still be true"),
]
LC_LENSES = [
    ("mic-camera-denied", "worker", "phone-390", ["AV", "F"], ["A", "U"], "person",
     "You refused the microphone or the camera once, and this page still has to be usable",
     ["voice-journal.html", "logbook.html", "assistant.html", "asset-hub.html", "shift-brain.html",
      "inventory.html", "resume.html", "community.html"]),
    ("second-hive", "worker", "phone-390", ["AU", "S"], ["I", "A"], "contract",
     "The platform must keep a person's two hives apart on this page, in both directions",
     ["hive.html", "logbook.html", "pm-scheduler.html", "alert-hub.html", "analytics.html",
      "inventory.html", "asset-hub.html", "dayplanner.html"]),
    ("year-2-aging", "fleet-supervisor", "desktop-1280", ["D", "LB"], ["A", "F"], "person",
     "After two years of history this page is still a page, and still says which period it is showing",
     ["analytics.html", "logbook.html", "pm-scheduler.html", "asset-hub.html", "audit-log.html",
      "analytics-report.html", "inventory.html", "skillmatrix.html"]),
    ("leaving", "adversary", "desktop-1280", ["S", "L"], ["I"], "contract",
     "The platform must let a person take their record and go, and must be honest to those who remain",
     ["hive.html", "audit-log.html", "resume.html", "achievements.html", "community.html",
      "public-feed.html", "logbook.html", "marketplace-seller-profile.html"]),
    ("two-tabs", "worker", "desktop-1280", ["D", "C"], ["I", "F"], "contract",
     "The platform must not let two tabs or two people overwrite each other silently on this page",
     ["logbook.html", "inventory.html", "pm-scheduler.html", "project-manager.html", "hive.html",
      "asset-hub.html", "marketplace-seller.html", "dayplanner.html"]),
    ("export-import", "fleet-supervisor", "desktop-1280", ["D", "A"], ["F", "I"], "person",
     "What this page exports can be read back in, and means the same thing on the way home",
     ["analytics-report.html", "logbook.html", "inventory.html", "asset-hub.html", "project-report.html",
      "audit-log.html", "skillmatrix.html", "integrations.html"]),
    ("notification-storm", "fleet-supervisor", "phone-390", ["A", "C"], ["A", "U"], "person",
     "Twenty alerts in an hour does not make this page unusable, and quiet hours are honoured",
     ["alert-hub.html", "logbook.html", "community.html", "hive.html", "dayplanner.html",
      "pm-scheduler.html", "marketplace.html", "index.html"]),
    ("version-skew", "worker", "phone-390", ["H", "AV"], ["A", "F"], "person",
     "A release lands while this page is open, and it neither breaks nor quietly serves yesterday",
     ["logbook.html", "index.html", "pm-scheduler.html", "alert-hub.html", "analytics.html",
      "inventory.html", "asset-hub.html", "community.html"]),
]
LAYER_LENS = {
    "D": ("The platform must be able to show where this page's data came from and what wrote it last", ["F"]),
    "S": ("The platform must refuse, on this page, a person who is not entitled to what it shows", ["I"]),
    "AU": ("The platform must keep this page's identity honest when a session ends or a role changes", ["I"]),
    "AV": ("The platform must keep this page truthful when the model or the pipeline behind it is wrong", ["I", "A"]),
    "A": ("The platform must keep this page working when the service behind it answers slowly or not at all", ["A"]),
    "C": ("The platform must state which clock and which period this page's figures belong to", ["I", "A"]),
    "H": ("The platform must serve this page correctly from the edge - headers, caching and offline included", ["A"]),
    "L": ("The platform must record who did what on this page, in a trail somebody can read later", ["I"]),
    "LB": ("The platform must keep this page responsive as its data grows past the size it was designed for", ["A"]),
    "RL": ("The platform must bound what this page can consume, and say so when it has", ["I", "A"]),
    "CI": ("The platform must catch this page's regressions before a person meets them", ["A"]),
    "CA": ("The platform must speak, on this page, the words a Philippine maintenance crew uses", ["U"]),
    "F": ("The platform must render this page's contract - the shapes, the states and the escapes it promises", ["U", "F"]),
}
DF_ROWS = [
    ("engineering-design.html", ["F", "D"], ["F", "U"], "person",
     "When this page has nothing to show yet it says why, and what to do first - the wave-2 walk found it silent"),
    ("report-sender.html", ["F", "D"], ["F", "U"], "person",
     "When this page has nothing to send yet it says why, and what to do first - the wave-2 walk found it silent"),
    ("assistant.html", ["AV", "S"], ["I"], "contract",
     "The platform must not promise an answer grounded in this hive's live data to a person who can read none of it"),
    ("hive.html", ["AU", "S"], ["I"], "contract",
     "The platform must tell a genuinely revoked member what happened, from a real revocation and not an injected id"),
]

CODES = {
    "JN": ("Full diverse journeys", "person"),
    "LN": ("Learn articles to full UFAI", "person"),
    "CL": ("Calculators to full UFAI", "contract"),
    "FN": ("Edge-function contracts", "contract"),
    "SC": ("Shared components as subjects", "person"),
    # ★THE SEEDER'S CAP WAS SMALLER THAN THE PROVER'S ROSTER. _shared_components() ends with `[:14]` while
    # tools/prove_shared_components.mjs carries a declared contract for NINETEEN pieces and walks every one,
    # so the wave produced 20 verdicts - about nav-hub.js (loaded by 31 pages), device-fingerprint.js (33),
    # companion-launcher.js (29), button-lock.js and impact-preview.js - with no row to be written into.
    # They are a SEPARATE code rather than more W3-SC rows because the validator's ids are POSITIONAL and
    # grouped by wave: inserting twenty rows into the SC block would renumber every row after it and orphan
    # every basis that cites one. An extension wave sorts last in both the file and the plan, so it costs
    # nothing already banked. Added by tools/extend_wave3_shared_components.py, 2026-09-08.
    "SC2": ("Shared components the first roster capped out", "person"),
    "PG": ("Persona x device x entry gaps", "person"),
    "LC": ("Lifecycle lenses", "person"),
    "AR": ("Empty page x layer cells", "contract"),
    "DF": ("Wave-2 deferred carry-over", "person"),
}


# ── measured rosters (frozen once the wave is seeded) ─────────────────────────────────────────────
def _root_pages() -> list[str]:
    return sorted(f for f in os.listdir(ROOT) if f.endswith(".html") and not f.startswith("_"))


def _glob(pattern: str) -> list[str]:
    return sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in ROOT.glob(pattern))


def _ufai_by_page(existing: list[dict]) -> dict[str, Counter]:
    out: dict[str, Counter] = {}
    for t in existing:
        if t.get("status") == "descoped":
            continue
        for p in (t.get("pages") or []):
            c = out.setdefault(p, Counter())
            for u in (t.get("ufai") or []):
                c[u] += 1
    return out


def _layers_by_page(existing: list[dict]) -> dict[str, set]:
    out: dict[str, set] = {}
    for t in existing:
        if t.get("status") == "descoped":
            continue
        for p in (t.get("pages") or []):
            out.setdefault(p, set()).update(t.get("layers") or [])
    return out


def _axis_by_page(existing: list[dict], field: str) -> dict[str, set]:
    out: dict[str, set] = {}
    for t in existing:
        if t.get("status") == "descoped":
            continue
        for p in (t.get("pages") or []):
            out.setdefault(p, set()).add(t.get(field) or "?")
    return out


def _edge_functions() -> list[str]:
    d = ROOT / "supabase" / "functions"
    return sorted(x.name for x in d.iterdir() if x.is_dir() and not x.name.startswith("_")) if d.is_dir() else []


def _shared_components(existing: list[dict]) -> list[str]:
    """The 14: every root .js a page actually loads that NO row has ever named, plus the most-loaded
    shared chrome, which today is graded only through its host pages."""
    loads: Counter = Counter()
    for h in _root_pages():
        try:
            s = (ROOT / h).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.findall(r'<script[^>]+src="([^"]+\.js)"', s):
            if not m.startswith("http"):
                loads[m.split("?")[0].lstrip("/")] += 1
    named = " ".join((t.get("title", "") + " " + (t.get("story") or "") + " " + (t.get("basis") or "")).lower()
                     for t in existing)
    never = [j for j in sorted(loads) if "/" not in j and j.lower() not in named]
    chrome = [j for j, n in loads.most_common() if "/" not in j and j not in never][:5]
    return (never + chrome)[:14]


def _short(page: str) -> str:
    return page.replace("/index.html", "").replace("learn/", "").replace("tools/", "").replace(".html", "").replace("-", " ")


# ── the plan ──────────────────────────────────────────────────────────────────────────────────────
def _jn_rows() -> list[dict]:
    """The journey grid: four tiers over the 32 archetypes. Pure enumeration - no measured roster, so
    it is stable across seeding."""
    rows: list[dict] = []
    by_code = {a[0]: a for a in ARCHETYPES}

    def emit(a, vertical, tier, device, language, moment, condition, entry, suffix, story_extra, pages=None):
        code, stage, scope, title, pgs, layers, ufai, persona, pair, base_entry, fns, jobtobedone = a
        t = f"{title} - {vertical}" + (f" · {suffix}" if suffix else "")
        row = {"wave": f"{PREFIX}-JN", "title": t, "pages": list(pages or pgs), "layers": list(layers),
               "ufai": list(ufai), "persona": persona, "device": device, "entry": entry or base_entry,
               "framing": "contract" if pair.count(" x ") and code in ("J14", "J26", "J27") else "person",
               "story": f"{jobtobedone}; {story_extra}" if story_extra else jobtobedone,
               "journey": {"archetype": code, "stage": stage, "vertical": vertical, "pair": pair,
                           "language": language, "moment": moment, "condition": condition, "tier": tier,
                           "pages": list(pages or pgs)}}
        if fns:
            row["functions"] = list(fns)
        rows.append(row)

    def cast(a) -> list[str]:
        scope = a[2]
        return {"all": HIVES, "plant": PLANT, "fleet": FLEET, "solo": SOLO, "platform": PLATFORM,
                "pair": [f"{x} buying from {y}" for x, y in PAIRS],
                "multi": [f"{x} and {y}, one person in both" for x, y in MULTI],
                "public": [f"{d}" for _e, d in PUBLIC_ENTRIES],
                "replay": [f"the {by_code[b][3].split(':')[0].lower()} of {HIVES[i]}" for i, b in enumerate(REPLAY_BASES)],
                }[scope]

    # ── tier A: the base cast, phone, English, the hive's present moment
    for a in ARCHETYPES:
        code, scope = a[0], a[2]
        for i, vertical in enumerate(cast(a)):
            entry = PUBLIC_ENTRIES[i][0] if scope == "public" else None
            pages = by_code[REPLAY_BASES[i]][4] if scope == "replay" else None
            extra = f"walked {CONDITIONS[i][1]}" if scope == "replay" else ""
            emit(a, vertical, "A", "phone-390", "en", "present",
                 CONDITIONS[i][0] if scope == "replay" else "normal", entry, "", extra, pages)

    # ── tier B: the same stories on a desktop, and in Filipino on both devices
    for a in ARCHETYPES:
        if a[0] == "J16":       # the degraded replay is already a variant; do not cube it
            continue
        scope = a[2]
        for i, vertical in enumerate(cast(a)):
            entry = PUBLIC_ENTRIES[i][0] if scope == "public" else None
            for device, lang, label, extra in (
                    ("desktop-1280", "en", "on a desktop", "the same story with the room a 1280 screen gives it"),
                    ("phone-390", "fil", "sa Filipino, sa telepono", "the same story read Filipino-first on a phone"),
                    ("desktop-1280", "fil", "sa Filipino, sa desktop", "the same story read Filipino-first on a desktop")):
                emit(a, vertical, "B", device, lang, "present", "normal", entry, label, extra)

    # ── tier C: the overlays, spread across the cast so no hive carries them all
    overlay_arches = [a for a in ARCHETYPES if a[2] in ("all", "plant")]
    for n, a in enumerate(overlay_arches):
        cs = cast(a)
        pick = lambda k: cs[(n + k) % len(cs)]                                    # noqa: E731
        if a[0] not in REPLAY_BASES:                                              # J16 owns these three
            for k, (cond, desc) in enumerate(CONDITIONS):
                emit(a, pick(k), "C", "phone-390", "en", "present", cond, None, desc, f"the same story {desc}")
        for k, (moment, desc) in enumerate(MOMENTS):
            emit(a, pick(k), "C", "phone-390", "en", moment, "normal", None, desc, f"the same story {desc}")
        for k, (entry, desc) in enumerate(OVERLAY_ENTRIES):
            emit(a, pick(k), "C", "phone-390", "en", "present", "normal", entry, desc, f"the same story, {desc}")
        for k, (who, device, desc) in enumerate(ASSISTIVE):
            emit(a, pick(k), "C", device, "en", "present", "normal", None, who, desc)
        if a[0] in TABLET_ARCHES:
            device, desc = WIDE[TABLET_ARCHES.index(a[0]) % len(WIDE)]
            emit(a, pick(0), "C", device, "en", "present", "normal",
                 "qr-print" if device == "fixed-kiosk-print" else None, desc, f"the same story {desc}")

    # ── tier D: the whole lifetimes - >=8 pages, >=5 layers, >=3 moments
    for title, chain, vertical in LIFETIMES:
        pages, layers, fns = [], [], []
        for c in chain:
            a = by_code[c]
            for p in a[4]:
                if p not in pages:
                    # ★AN ARCHETYPE'S ENTRY PAGE STOPS BEING AN ENTRY WHEN IT IS CHAINED (2026-09-10).
                    # J31's own path BEGINS at resume.html, which is correct for a story that starts
                    # there - but chained after J7 into "one worker's career", resume.html lands in the
                    # middle, entered from whatever page happened to precede it (index.html). resume is
                    # hidden from the nav and parented by achievements/skillmatrix, so the walk reported
                    # "1 hop goes straight to a destination the platform parents elsewhere - this
                    # archetype's PATH skips the intended route, it is not a navigation gap". The prover
                    # was right and the path was wrong: three Tier D rows sat red on a defect in their
                    # own spec. Concatenating page lists is not composing a journey - a route has to be
                    # walkable at the join. So when a page nobody's nav offers is about to be entered
                    # from a page that does not link to it, its parent is inserted first.
                    if pages and p not in _NAV_OFFERED:
                        prev = pages[-1]
                        if not _hop_ok(prev, p):
                            for hop in _entry_chain(p, prev, pages):
                                pages.append(hop)
                    pages.append(p)
            for l in a[5]:
                if l not in layers:
                    layers.append(l)
            for f in a[10]:
                if f not in fns:
                    fns.append(f)
        row = {"wave": f"{PREFIX}-JN", "title": f"{title} · the whole story end to end",
               "pages": pages, "layers": layers, "ufai": ["F", "A", "I", "U"],
               "persona": "fleet-supervisor", "device": "desktop-1280", "entry": "hub-nav", "framing": "person",
               "story": "the chained lifetime: " + " -> ".join(chain)
                        + "; walked across day one, month three and year two, each step's transition and each write's"
                          " persisted effect receipted",
               "journey": {"archetype": "+".join(chain), "stage": "lifetime", "vertical": vertical, "pair": "",
                           "language": "en", "moment": "day-1+month-3+year-2", "condition": "normal",
                           "tier": "D", "pages": pages}}
        if fns:
            row["functions"] = fns
        rows.append(row)
    return rows


def plan(existing: list[dict] | None = None) -> list[dict]:
    """Every row this wave creates, code-major, in a stable order.

    ★THE MEASURED ROSTERS FREEZE ON SEEDING. Every deficit below (a learn article's missing UFAI
    dimensions, a page's missing persona, an empty page x layer cell) is CLOSED by the rows this file
    writes, so re-measuring after the write would yield a different, shorter plan - and the gate derives
    its expected ids from this very function. Once any W3 row exists, the plan IS those rows.
    """
    if existing is None:
        try:
            existing = json.loads(REGISTRY.read_text(encoding="utf-8"))["trajectories"]
        except Exception:
            existing = []
    seeded = [t for t in existing if str(t.get("id", "")).startswith(PREFIX)]
    if seeded:
        keep = ("wave", "title", "pages", "layers", "ufai", "persona", "device", "entry", "framing",
                "story", "journey", "functions")
        return [{k: t[k] for k in keep if k in t} for t in seeded]

    scoped = [t for t in existing if t.get("status") != "descoped"]
    by_page = _ufai_by_page(scoped)
    rows: list[dict] = []

    def emit(code: str, title: str, pages: list[str], layers: list[str], ufai: list[str], persona: str,
             device: str, entry: str, story: str, framing: str | None = None, fns: list[str] | None = None):
        r = {"wave": f"{PREFIX}-{code}", "title": title, "pages": pages, "layers": layers, "ufai": ufai,
             "persona": persona, "device": device, "entry": entry,
             "framing": framing or CODES[code][1], "story": story}
        if fns:
            r["functions"] = fns
        rows.append(r)

    # JN — the journeys
    rows.extend(_jn_rows())

    # LN — every learn article's missing UFAI dimensions
    for page in _glob("learn/*/index.html"):
        have = by_page.get(page, Counter())
        for dim in "FAI":
            if have.get(dim, 0) == 0:
                lens, layers = LN_LENSES[dim]
                emit("LN", f"{lens} - {_short(page)}", [page], layers, [dim], "anon", "phone-390",
                     "search-arrival",
                     "a reader who arrived from a search result and will judge the platform by this page")

    # CL — every calculator's missing UFAI dimensions
    for page in _glob("tools/*/index.html"):
        have = by_page.get(page, Counter())
        for dim in "FAI":
            if have.get(dim, 0) == 0:
                lens, layers = CL_LENSES[dim]
                emit("CL", f"{lens} - {_short(page)}", [page], layers, [dim], "anon", "phone-390",
                     "search-arrival",
                     "an engineer who will put this number in a drawing, and a standard that will be checked")

    # FN — three contract rows per edge function
    for fn in _edge_functions():
        for dim, lens, layers, framing in FN_LENSES:
            emit("FN", f"{lens} - {fn}", [], layers, [dim], "machine-client", "any", "direct",
                 f"supabase/functions/{fn}: walked by invoke and by PostgREST as the caller's own persona, "
                 "never as the owner connection", framing, [fn])

    # SC — the shared pieces, as subjects rather than as somebody else's page
    for js in _shared_components(scoped):
        for dim, lens, layers in SC_LENSES:
            emit("SC", f"{lens} - {js}", [], layers, [dim], "any", "phone-390", "hub-nav",
                 f"{js}: walked on three host pages (phone, desktop, wall display), because shared chrome is "
                 "graded once and styled before paint")

    # PG — the persona / device / entry cells a root page has never been walked in
    per = _axis_by_page(scoped, "persona")
    dev = _axis_by_page(scoped, "device")
    ent = _axis_by_page(scoped, "entry")
    for page in _root_pages():
        if page in NOT_A_DESTINATION:
            continue
        for persona, device, entry, layers, lens in PG_CELLS:
            if persona == "anon" and page not in PUBLIC_PAGES:
                continue
            if entry == "qr-print" and page not in PRINT_PAGES:
                continue
            axis, have = ((persona, per), (device, dev), (entry, ent))[
                0 if persona in ("new-user", "returner", "anon") else (1 if device == "tablet-768" else 2)]
            if axis in have.get(page, set()):
                continue
            emit("PG", f"{lens} - {_short(page)}", [page], layers, ["A", "U"], persona, device, entry,
                 f"cell {persona}@{device} arriving by {entry}: this page had never been walked in it")

    # LC — the lifecycle lenses the whole program is thin on
    for key, persona, device, layers, ufai, framing, lens, roster in LC_LENSES:
        for page in roster:
            emit("LC", f"{lens} - {_short(page)}", [page], layers, ufai, persona, device, "hub-nav",
                 f"lifecycle lens {key}: the program carried fewer than 30 rows on this shape before wave 3",
                 framing)

    # AR — the empty (page, layer) cells, where the layer applies to a person-facing page
    lay = _layers_by_page(scoped)
    for page in _root_pages():
        if page in NOT_A_DESTINATION:
            continue
        for layer in LAYER_SET:
            if layer in lay.get(page, set()):
                continue
            lens, ufai = LAYER_LENS[layer]
            emit("AR", f"{lens} - {_short(page)}", [page], [layer], ufai, "any", "any", "hub-nav",
                 f"layer {layer} had no row on this page when wave 3 was seeded")

    # DF — what wave 2 found and deliberately left
    for page, layers, ufai, framing, lens in DF_ROWS:
        emit("DF", f"{lens} - {_short(page)}", [page], layers, ufai, "worker", "phone-390", "hub-nav",
             "carried over from the wave-2 walks, which found it and deferred it by name", framing)
    return rows


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    existing = doc["trajectories"]
    have = {t["id"] for t in existing}
    rows = plan(existing)

    per_code: Counter = Counter(r["wave"] for r in rows)
    print("  %-8s %-40s %8s" % ("code", "direction", "rows"))
    for code, (name, _f) in CODES.items():
        print("  %-8s %-40s %8d" % (f"{PREFIX}-{code}", name, per_code.get(f"{PREFIX}-{code}", 0)))
    print("  %-8s %-40s %8d" % ("", "TOTAL new trajectories", len(rows)))

    jn = [r for r in rows if r["wave"] == f"{PREFIX}-JN"]
    tiers = Counter(r["journey"]["tier"] for r in jn)
    print("\n  JN tiers: " + " · ".join(f"{k} {tiers[k]}" for k in "ABCD")
          + f" | archetypes {len({r['journey']['archetype'] for r in jn if '+' not in r['journey']['archetype']})}"
          + f" | verticals {len({r['journey']['vertical'] for r in jn})}"
          + f" | >=4 pages {sum(1 for r in jn if len(r['pages']) >= 4)}")
    ufai_mix: Counter = Counter(x for r in rows for x in r["ufai"])
    print("  UFAI mix of the new rows: " + " · ".join(f"{k} {ufai_mix.get(k, 0)}" for k in "UFAI"))
    scoped = [t for t in existing if t.get("status") != "descoped"]
    after = len(scoped) + len(rows)
    print(f"  program: {len(scoped)} in scope today -> {after} after seeding "
          f"({100.0 * len(scoped) / after:.1f}% closed on seed day)")

    nxt = 1
    created = []
    for r in rows:
        while f"{PREFIX}{nxt}" in have:
            nxt += 1
        rid = f"{PREFIX}{nxt}"
        have.add(rid)
        created.append(dict({"id": rid, "status": "specced", "pct": 5}, **r))

    if args.dry_run:
        print()
        for code in CODES:
            first = next((c for c in created if c["wave"] == f"{PREFIX}-{code}"), None)
            if first:
                print(f"  {first['id']:<8} {first['title'][:104]}")
        d = next((c for c in created if c.get("journey", {}).get("tier") == "D"), None)
        if d:
            print(f"  tier D  {d['id']} · {len(d['pages'])} pages · {len(d['layers'])} layers · {d['title'][:70]}")
        print("  (nothing written)")
        return 0

    seen = {(t.get("title"), tuple(t.get("pages") or [])) for t in existing}
    fresh = [c for c in created if (c["title"], tuple(c["pages"])) not in seen]
    doc["trajectories"] = existing + fresh
    doc["count"] = len(doc["trajectories"])
    _atomic_write(REGISTRY, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    # the critic bank grows with the registry, from ONE place, and never rewrites an existing row
    from critic_seed_missing import seed_missing  # noqa: E402
    seed_missing()
    print(f"\n  wrote {len(fresh)} new row(s) into {REGISTRY.name} (registry now {doc['count']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
